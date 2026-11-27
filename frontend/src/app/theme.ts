import { InputWrapper, createTheme } from '@mantine/core';

/**
 * Regla de formularios del proyecto: la ayuda (`description`) va debajo del campo, para que en filas de varias
 * columnas todos los campos empiecen a la misma altura, tengan ayuda o no (`frontend.instructions.md`).
 */
export const INPUT_WRAPPER_ORDER: ('label' | 'input' | 'description' | 'error')[] = [
  'label',
  'input',
  'description',
  'error',
];

export const theme = createTheme({
  primaryColor: 'blue',
  defaultRadius: 'md',
  components: {
    InputWrapper: InputWrapper.extend({ defaultProps: { inputWrapperOrder: INPUT_WRAPPER_ORDER } }),
  },
});
