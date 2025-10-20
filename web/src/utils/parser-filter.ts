// Modern parsers that work with MinerU/DOTS
export const ModernParsers = ['smart', 'regex', 'title', 'parent_child'];

/**
 * Filter parser list based on layout_recognize value
 */
export function filterParsersByLayoutRecognize(
  parserValue: string,
  layoutRecognize?: string,
): boolean {
  // If layout_recognize is MinerU or DOTS, only show modern parsers
  if (layoutRecognize === 'MinerU' || layoutRecognize === 'DOTS') {
    return ModernParsers.includes(parserValue);
  }

  // If layout_recognize is set to other values, only show non-modern parsers
  if (
    layoutRecognize &&
    layoutRecognize !== 'MinerU' &&
    layoutRecognize !== 'DOTS'
  ) {
    return !ModernParsers.includes(parserValue);
  }

  // If layout_recognize is not set, show all (backward compatibility)
  return true;
}
