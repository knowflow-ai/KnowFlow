#
#  Copyright 2025 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

import copy
import re
from io import BytesIO

from PIL import Image

from api.db import LLMType
from api.db.services.llm_service import LLMBundle
from deepdoc.parser.pdf_parser import VisionParser
from rag.nlp import tokenize, is_english
from rag.nlp import rag_tokenizer
from deepdoc.parser import PdfParser, PptParser, PlainParser, MinerUParser, DOTSParser
from PyPDF2 import PdfReader as pdf2_read


class Ppt(PptParser):
    def __call__(self, fnm, from_page, to_page, callback=None):
        txts = super().__call__(fnm, from_page, to_page)

        callback(0.5, "Text extraction finished.")
        import aspose.slides as slides
        import aspose.pydrawing as drawing
        imgs = []
        with slides.Presentation(BytesIO(fnm)) as presentation:
            for i, slide in enumerate(presentation.slides[from_page: to_page]):
                try:
                    with BytesIO() as buffered:
                        slide.get_thumbnail(
                            0.1, 0.1).save(
                            buffered, drawing.imaging.ImageFormat.jpeg)
                        buffered.seek(0)
                        imgs.append(Image.open(buffered).copy())
                except RuntimeError as e:
                    raise RuntimeError(f'ppt parse error at page {i+1}, original error: {str(e)}') from e
        assert len(imgs) == len(
            txts), "Slides text and image do not match: {} vs. {}".format(len(imgs), len(txts))
        callback(0.9, "Image extraction finished")
        self.is_english = is_english(txts)
        return [(txts[i], imgs[i]) for i in range(len(txts))]


class Pdf(PdfParser):
    def __init__(self):
        super().__init__()

    def __garbage(self, txt):
        txt = txt.lower().strip()
        if re.match(r"[0-9\.,%/-]+$", txt):
            return True
        if len(txt) < 3:
            return True
        return False

    def __call__(self, filename, binary=None, from_page=0,
                 to_page=100000, zoomin=3, callback=None):
        from timeit import default_timer as timer
        start = timer()
        callback(msg="OCR started")
        self.__images__(filename if not binary else binary,
                        zoomin, from_page, to_page, callback)
        callback(msg="Page {}~{}: OCR finished ({:.2f}s)".format(from_page, min(to_page, self.total_page), timer() - start))
        assert len(self.boxes) == len(self.page_images), "{} vs. {}".format(
            len(self.boxes), len(self.page_images))
        res = []
        for i in range(len(self.boxes)):
            lines = "\n".join([b["text"] for b in self.boxes[i]
                              if not self.__garbage(b["text"])])
            res.append((lines, self.page_images[i]))
        callback(0.9, "Page {}~{}: Parsing finished".format(
            from_page, min(to_page, self.total_page)))
        return res


class PlainPdf(PlainParser):
    def __call__(self, filename, binary=None, from_page=0,
                 to_page=100000, callback=None, **kwargs):
        self.pdf = pdf2_read(filename if not binary else BytesIO(binary))
        page_txt = []
        for page in self.pdf.pages[from_page: to_page]:
            page_txt.append(page.extract_text())
        callback(0.9, "Parsing finished")
        return [(txt, None) for txt in page_txt]


def chunk(filename, binary=None, from_page=0, to_page=100000,
          lang="Chinese", callback=None, parser_config=None, **kwargs):
    """
    The supported file formats are pdf, pptx.
    Every page will be treated as a chunk. And the thumbnail of every page will be stored.
    PPT file will be parsed by using this method automatically, setting-up for every PPT file is not necessary.
    """
    if parser_config is None:
        parser_config = {}
    eng = lang.lower() == "english"
    doc = {
        "docnm_kwd": filename,
        "title_tks": rag_tokenizer.tokenize(re.sub(r"\.[a-zA-Z]+$", "", filename))
    }
    doc["title_sm_tks"] = rag_tokenizer.fine_grained_tokenize(doc["title_tks"])
    res = []
    if re.search(r"\.pptx?$", filename, re.IGNORECASE):
        ppt_parser = Ppt()
        for pn, (txt, img) in enumerate(ppt_parser(
                filename if not binary else binary, from_page, 1000000, callback)):
            d = copy.deepcopy(doc)
            pn += from_page
            d["image"] = img
            d["doc_type_kwd"] = "image"
            d["page_num_int"] = [pn + 1]
            d["top_int"] = [0]
            d["position_int"] = [(pn + 1, 0, img.size[0], 0, img.size[1])]
            tokenize(d, txt, eng)
            res.append(d)
        return res
    elif re.search(r"\.pdf$", filename, re.IGNORECASE):
        layout_recognizer = parser_config.get("layout_recognize", "DeepDOC")
        if layout_recognizer == "MinerU":
            logging.info("Using MinerU parser for PDF (presentation mode)")
            pdf_parser = MinerUParser()
            parsed_sections, _ = pdf_parser(
                filename if not binary else binary,
                from_page=from_page,
                to_page=to_page,
                chunk_level='semantic',
                **kwargs
            )
            # MinerU 返回语义块列表，需要按页分组并合并
            # presentation 模式要求每页作为一个 chunk
            from collections import defaultdict
            page_texts = defaultdict(list)
            for text_with_tag, _ in parsed_sections:
                # 从 position tag 提取页码: @@page_num\t...##
                match = re.match(r'@@(\d+)\t', text_with_tag)
                if match:
                    page_num = int(match.group(1))
                    clean_text = pdf_parser.remove_tag(text_with_tag)
                    page_texts[page_num].append(clean_text)
            # 生成连续的页面列表（从 from_page 到 to_page）
            # 与 DeepDOC 保持一致：即使某页没内容也要有空元素
            sections = []
            for page_num in range(from_page, to_page + 1):
                if page_num in page_texts:
                    page_text = "\n".join(page_texts[page_num])
                    sections.append((page_text, None))
                elif page_num < max(page_texts.keys(), default=from_page):
                    # 中间缺失的页，添加空内容
                    sections.append(("", None))
                else:
                    # 超出解析范围，停止
                    break
        elif layout_recognizer == "DOTS":
            logging.info("Using DOTS parser for PDF (presentation mode)")
            pdf_parser = DOTSParser()
            parsed_sections, _ = pdf_parser(
                filename if not binary else binary,
                from_page=from_page,
                to_page=to_page,
                chunk_level='semantic',
                **kwargs
            )
            # DOTS 返回语义块列表，需要按页分组并合并
            # presentation 模式要求每页作为一个 chunk
            from collections import defaultdict
            page_texts = defaultdict(list)
            for text_with_tag, _ in parsed_sections:
                # 从 position tag 提取页码: @@page_num\t...##
                match = re.match(r'@@(\d+)\t', text_with_tag)
                if match:
                    page_num = int(match.group(1))
                    clean_text = pdf_parser.remove_tag(text_with_tag)
                    page_texts[page_num].append(clean_text)
            # 生成连续的页面列表（从 from_page 到 to_page）
            # 与 DeepDOC 保持一致：即使某页没内容也要有空元素
            sections = []
            for page_num in range(from_page, to_page + 1):
                if page_num in page_texts:
                    page_text = "\n".join(page_texts[page_num])
                    sections.append((page_text, None))
                elif page_num < max(page_texts.keys(), default=from_page):
                    # 中间缺失的页，添加空内容
                    sections.append(("", None))
                else:
                    # 超出解析范围，停止
                    break
        elif layout_recognizer == "DeepDOC":
            pdf_parser = Pdf()
            sections = pdf_parser(filename, binary, from_page=from_page, to_page=to_page, callback=callback)
        elif layout_recognizer == "Plain Text":
            pdf_parser = PlainParser()
            sections, _ = pdf_parser(filename if not binary else binary, from_page=from_page, to_page=to_page,
                                      callback=callback)
        else:
            vision_model = LLMBundle(kwargs["tenant_id"], LLMType.IMAGE2TEXT, llm_name=layout_recognizer, lang=lang)
            pdf_parser = VisionParser(vision_model=vision_model, **kwargs)
            sections, _ = pdf_parser(filename if not binary else binary, from_page=from_page, to_page=to_page,
                                      callback=callback)

        callback(0.8, "Finish parsing.")
        for pn, (txt, img) in enumerate(sections):
            d = copy.deepcopy(doc)
            pn += from_page
            if img:
                d["image"] = img
            d["page_num_int"] = [pn + 1]
            d["top_int"] = [0]
            d["position_int"] = [(pn + 1, 0, img.size[0] if img else 0, 0, img.size[1] if img else 0)]
            tokenize(d, txt, eng)
            res.append(d)
        return res

    raise NotImplementedError(
        "file type not supported yet(pptx, pdf supported)")


if __name__ == "__main__":
    import sys

    def dummy(a, b):
        pass
    chunk(sys.argv[1], callback=dummy)
