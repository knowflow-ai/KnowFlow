import { DocumentParserType } from '@/constants/knowledge';
import { useHandleChunkMethodSelectChange } from '@/hooks/logic-hooks';
import { useSelectParserList } from '@/hooks/user-setting-hooks';
import {
  ModernLayoutRecognizers,
  ModernParsers,
  filterParsersByLayoutRecognize,
} from '@/utils/parser-filter';
import { Form, FormInstance } from 'antd';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

const ParserListMap = new Map([
  [
    ['pdf'],
    [
      DocumentParserType.Naive,
      DocumentParserType.Resume,
      DocumentParserType.Manual,
      DocumentParserType.Paper,
      DocumentParserType.Book,
      DocumentParserType.Laws,
      DocumentParserType.Presentation,
      DocumentParserType.One,
      DocumentParserType.Qa,
      DocumentParserType.KnowledgeGraph,
      DocumentParserType.Smart,
      DocumentParserType.Regex,
      DocumentParserType.ParentChild,
      DocumentParserType.Title,
    ],
  ],
  [
    ['doc', 'docx'],
    [
      DocumentParserType.Naive,
      DocumentParserType.Resume,
      DocumentParserType.Book,
      DocumentParserType.Laws,
      DocumentParserType.One,
      DocumentParserType.Qa,
      DocumentParserType.Manual,
      DocumentParserType.KnowledgeGraph,
      DocumentParserType.Smart,
      DocumentParserType.Regex,
      DocumentParserType.ParentChild,
      DocumentParserType.Title,
    ],
  ],
  [
    ['xlsx', 'xls'],
    [
      DocumentParserType.Naive,
      DocumentParserType.Qa,
      DocumentParserType.Table,
      DocumentParserType.One,
      DocumentParserType.KnowledgeGraph,
    ],
  ],
  [
    ['ppt', 'pptx'],
    [
      DocumentParserType.Presentation,
      DocumentParserType.Smart,
      DocumentParserType.Regex,
      DocumentParserType.ParentChild,
      DocumentParserType.Title,
    ],
  ],
  [
    ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'tif', 'tiff', 'webp', 'svg', 'ico'],
    [DocumentParserType.Picture],
  ],
  [
    ['txt'],
    [
      DocumentParserType.Naive,
      DocumentParserType.Resume,
      DocumentParserType.Book,
      DocumentParserType.Laws,
      DocumentParserType.One,
      DocumentParserType.Qa,
      DocumentParserType.Table,
      DocumentParserType.KnowledgeGraph,
    ],
  ],
  [
    ['csv'],
    [
      DocumentParserType.Naive,
      DocumentParserType.Resume,
      DocumentParserType.Book,
      DocumentParserType.Laws,
      DocumentParserType.One,
      DocumentParserType.Qa,
      DocumentParserType.Table,
      DocumentParserType.KnowledgeGraph,
    ],
  ],
  [
    ['md'],
    [
      DocumentParserType.Naive,
      DocumentParserType.Qa,
      DocumentParserType.KnowledgeGraph,
      DocumentParserType.Smart,
      DocumentParserType.Regex,
      DocumentParserType.ParentChild,
      DocumentParserType.Title,
    ],
  ],
  [['json'], [DocumentParserType.Naive, DocumentParserType.KnowledgeGraph]],
  [['eml'], [DocumentParserType.Email]],
]);

const getParserList = (
  values: string[],
  parserList: Array<{
    value: string;
    label: string;
  }>,
  layoutRecognize?: string,
) => {
  return parserList.filter((x) => {
    // Must be in the values list
    if (!values?.some((y) => y === x.value)) {
      return false;
    }

    // Filter by layout_recognize
    return filterParsersByLayoutRecognize(x.value as string, layoutRecognize);
  });
};

export const useFetchParserListOnMount = (
  documentId: string,
  parserId: DocumentParserType,
  documentExtension: string,
  form: FormInstance,
) => {
  const [selectedTag, setSelectedTag] = useState<DocumentParserType>();
  const parserList = useSelectParserList();
  const handleChunkMethodSelectChange = useHandleChunkMethodSelectChange(form);

  // Watch layout_recognize value from parser_config
  const layoutRecognize = Form.useWatch(
    ['parser_config', 'layout_recognize'],
    form,
  );

  const nextParserList = useMemo(() => {
    const key = [...ParserListMap.keys()].find((x) =>
      x.some((y) => y === documentExtension),
    );
    if (key) {
      const values = ParserListMap.get(key);
      return getParserList(values ?? [], parserList, layoutRecognize);
    }

    return getParserList(
      [
        DocumentParserType.Naive,
        DocumentParserType.Resume,
        DocumentParserType.Book,
        DocumentParserType.Laws,
        DocumentParserType.One,
        DocumentParserType.Qa,
        DocumentParserType.Table,
      ],
      parserList,
      layoutRecognize,
    );
  }, [parserList, documentExtension, layoutRecognize]);

  // Use ref to track previous value and avoid triggering on initial mount
  const prevLayoutRecognizeRef = useRef<string | undefined>();
  const isInitialMount = useRef(true);

  // Auto-switch parser when layout_recognize changes
  useEffect(() => {
    // Skip on initial mount
    if (isInitialMount.current) {
      isInitialMount.current = false;
      prevLayoutRecognizeRef.current = layoutRecognize;
      return;
    }

    // Skip if values not ready or layout_recognize hasn't changed
    if (!layoutRecognize || !selectedTag) return;
    if (prevLayoutRecognizeRef.current === layoutRecognize) return;

    prevLayoutRecognizeRef.current = layoutRecognize;

    const isModernLayoutRecognizer =
      ModernLayoutRecognizers.includes(layoutRecognize);
    const isCurrentParserModern = ModernParsers.includes(selectedTag);

    // If layout_recognize is MinerU/DOTS/PaddleOCR but current parser is not modern, switch to smart
    if (isModernLayoutRecognizer && !isCurrentParserModern) {
      const smartParser = DocumentParserType.Smart;
      setSelectedTag(smartParser);
      handleChunkMethodSelectChange(smartParser);
    }
    // If layout_recognize is not MinerU/DOTS/PaddleOCR but current parser is modern, switch to naive
    else if (!isModernLayoutRecognizer && isCurrentParserModern) {
      const naiveParser = DocumentParserType.Naive;
      setSelectedTag(naiveParser);
      handleChunkMethodSelectChange(naiveParser);
    }
  }, [layoutRecognize, selectedTag, handleChunkMethodSelectChange]);

  useEffect(() => {
    setSelectedTag(parserId);
  }, [parserId, documentId]);

  const handleChange = (tag: string) => {
    handleChunkMethodSelectChange(tag);
    setSelectedTag(tag as DocumentParserType);
  };

  return { parserList: nextParserList, handleChange, selectedTag };
};

const hideAutoKeywords = [
  DocumentParserType.Qa,
  DocumentParserType.Table,
  DocumentParserType.Resume,
  DocumentParserType.KnowledgeGraph,
  DocumentParserType.Tag,
];

export const useShowAutoKeywords = () => {
  const showAutoKeywords = useCallback(
    (selectedTag: DocumentParserType | undefined) => {
      return hideAutoKeywords.every((x) => selectedTag !== x);
    },
    [],
  );

  return showAutoKeywords;
};
