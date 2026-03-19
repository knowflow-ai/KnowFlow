import {
  AutoKeywordsFormField,
  AutoQuestionsFormField,
} from '@/components/auto-keywords-form-field';
import EnableHeadingInContent from '@/components/enable-heading-in-content';
import { ExcelToHtmlFormField } from '@/components/excel-to-html-form-field';
import { LayoutRecognizeFormField } from '@/components/layout-recognize-form-field';
import { MaxTokenNumberFormField } from '@/components/max-token-number-from-field';
import PageRankFormField from '@/components/page-rank-form-field';
import GraphRagItems from '@/components/parse-configuration/graph-rag-form-fields';
import RaptorFormFields from '@/components/parse-configuration/raptor-form-fields';
import SplitLevel from '@/components/split-level';
import {
  ConfigurationFormContainer,
  MainContainer,
} from '../configuration-form-container';
import { TagItems } from '../tag-item';
import { ChunkMethodItem, EmbeddingModelItem } from './common-item';

export function TitleConfiguration() {
  return (
    <MainContainer>
      <ConfigurationFormContainer>
        <ChunkMethodItem></ChunkMethodItem>
        <LayoutRecognizeFormField></LayoutRecognizeFormField>
        <EmbeddingModelItem></EmbeddingModelItem>
        <MaxTokenNumberFormField initialValue={256}></MaxTokenNumberFormField>
        <EnableHeadingInContent></EnableHeadingInContent>
        <SplitLevel></SplitLevel>
      </ConfigurationFormContainer>
      <ConfigurationFormContainer>
        <PageRankFormField></PageRankFormField>
        <AutoKeywordsFormField></AutoKeywordsFormField>
        <AutoQuestionsFormField></AutoQuestionsFormField>
        <ExcelToHtmlFormField></ExcelToHtmlFormField>
        <TagItems></TagItems>
      </ConfigurationFormContainer>
      <ConfigurationFormContainer>
        <RaptorFormFields></RaptorFormFields>
      </ConfigurationFormContainer>
      <GraphRagItems></GraphRagItems>
    </MainContainer>
  );
}
