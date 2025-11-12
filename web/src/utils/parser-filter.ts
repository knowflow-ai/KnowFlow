// Modern parsers that work with MinerU/DOTS/PaddleOCR
export const ModernParsers = ['smart', 'regex', 'title', 'parent_child'];

// Layout recognizers that support modern parsers
export const ModernLayoutRecognizers = ['MinerU', 'DOTS', 'PaddleOCR'];

/**
 * Filter parser list based on layout_recognize value
 */
export function filterParsersByLayoutRecognize(
  parserValue: string,
  layoutRecognize?: string,
): boolean {
  // If layout_recognize is MinerU, DOTS, or PaddleOCR, only show modern parsers
  if (ModernLayoutRecognizers.includes(layoutRecognize || '')) {
    return ModernParsers.includes(parserValue);
  }

  // If layout_recognize is set to other values, only show non-modern parsers
  if (layoutRecognize && !ModernLayoutRecognizers.includes(layoutRecognize)) {
    return !ModernParsers.includes(parserValue);
  }

  // If layout_recognize is not set, show all (backward compatibility)
  return true;
}
