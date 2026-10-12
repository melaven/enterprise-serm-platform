import { Toaster as Sonner, type ToasterProps } from 'sonner';

const BASE =
  'group flex w-full items-start gap-3 rounded-sm border border-zinc-800 bg-black p-4 text-sm font-medium uppercase tracking-wider text-zinc-100 shadow-none';

/**
 * Плоские тосты: border Chrome, без теней. success — lime, error — красный #FF5C5C
 * (plum на чёрном ~1.9:1, нечитаем как текст; plum остаётся заливкой).
 * unstyled: true отключает собственные стили Sonner, весь вид задан классами ниже.
 */
export function Toaster(props: ToasterProps) {
  return (
    <Sonner
      theme="dark"
      position="bottom-right"
      gap={8}
      visibleToasts={4}
      closeButton={false}
      toastOptions={{
        unstyled: true,
        classNames: {
          toast: BASE,
          title: 'text-xs font-semibold uppercase tracking-wider',
          description: 'mt-1 text-xs normal-case tracking-normal text-zinc-400',
          success: '!text-lime',
          error: '!text-danger',
          warning: '!text-white',
          info: '!text-zinc-100',
          icon: 'mt-0.5 size-4 shrink-0',
          actionButton:
            'ml-auto h-8 rounded-sm bg-plum px-3 text-xs font-semibold uppercase tracking-wider text-white hover:bg-plum-deep',
          cancelButton:
            'ml-auto h-8 rounded-sm border border-zinc-700 px-3 text-xs font-semibold uppercase tracking-wider text-zinc-300 hover:bg-zinc-900',
        },
      }}
      {...props}
    />
  );
}
