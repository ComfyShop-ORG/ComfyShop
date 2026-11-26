import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, test } from 'vitest';
import { Field, Input, TextArea, Tooltip } from '@comfyshop/ui';

afterEach(cleanup);

function setup() {
  render(
    <Tooltip.Provider>
      <TextArea aria-label="提示词" />
      <Field label="步数" htmlFor="steps" help="控制生成步数">
        <Input id="steps" />
      </Field>
    </Tooltip.Provider>,
  );
  return {
    user: userEvent.setup(),
    prompt: screen.getByRole<HTMLTextAreaElement>('textbox', { name: '提示词' }),
    help: screen.getByRole('button', { name: '步数提示' }),
  };
}

test('hovering across a field hint does not take focus from the text being typed', async () => {
  const { user, prompt, help } = setup();
  await user.click(prompt);
  await user.keyboard('abc');
  await user.hover(help);
  expect(screen.getByRole('tooltip').textContent).toBe('控制生成步数');
  await user.unhover(help);
  expect(screen.queryByRole('tooltip')).toBeNull();
  await user.keyboard('def');
  expect(prompt.value).toBe('abcdef');
});

test('the hint is announced with the button and reopens after Escape', async () => {
  const { user, help } = setup();
  const description = document.getElementById(help.getAttribute('aria-describedby') ?? '');
  expect(description?.textContent).toBe('控制生成步数');
  await user.hover(help);
  await user.keyboard('{Escape}');
  expect(screen.queryByRole('tooltip')).toBeNull();
  // 指针还停在问号上：再点一次应当打开说明，而不是被上一次悬停吞掉。
  await user.click(help);
  expect(screen.getByRole('tooltip')).toBeTruthy();
});
