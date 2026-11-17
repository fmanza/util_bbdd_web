import { within } from '@testing-library/react';
import type { UserEvent } from '@testing-library/user-event';

/** Elige una operación en la lista del modal «Lanzar ejecución» (un `radiogroup` «Operación»). */
export async function chooseOperation(user: UserEvent, dialog: HTMLElement, title: string) {
  const rail = await within(dialog).findByRole('radiogroup', { name: 'Operación' });
  await user.click(within(rail).getByRole('radio', { name: title }));
}
