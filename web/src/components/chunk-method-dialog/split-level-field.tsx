import {
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useFormContext } from 'react-hook-form';
import { useTranslation } from 'react-i18next';

export function SplitLevelField() {
  const form = useFormContext();
  const { t } = useTranslation();

  const options = [
    { label: 'H1', value: 1 },
    { label: 'H2', value: 2 },
    { label: 'H3', value: 3 },
    { label: 'H4', value: 4 },
    { label: 'H5', value: 5 },
    { label: 'H6', value: 6 },
  ];

  return (
    <FormField
      control={form.control}
      name="parserConfig.split_level"
      render={({ field }) => {
        // Set default value if undefined
        if (typeof field.value === 'undefined') {
          form.setValue('parserConfig.split_level', 3);
        }

        return (
          <FormItem>
            <FormLabel>
              {t('knowledgeConfiguration.splitLevel', '标题分割层级')}
            </FormLabel>
            <FormControl>
              <Select
                value={String(field.value)}
                onValueChange={(value) => field.onChange(Number(value))}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {options.map((option) => (
                    <SelectItem key={option.value} value={String(option.value)}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </FormControl>
            <FormMessage />
          </FormItem>
        );
      }}
    />
  );
}
