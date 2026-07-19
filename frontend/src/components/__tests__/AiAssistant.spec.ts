import { flushPromises, mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import AiAssistant from '../AiAssistant.vue'

const apiMock = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
}))

const fetchMock = vi.fn()

const i18nMock = vi.hoisted(() => ({
  locale: { value: 'en' },
  t: vi.fn((key: string) => {
    const map: Record<string, string> = {
      'ai.assistantTitle': 'AI assistant',
      'ai.fabShort': 'AI',
      'ai.disabled': 'AI disabled',
      'ai.placeholder': 'Ask something',
      'ai.requestError': 'AI request error',
      'ai.thinkingStatic': 'AI is thinking',
    }
    return map[key] || key
  }),
}))

vi.mock('../../api/client', () => ({ default: apiMock }))
vi.mock('vue-i18n', () => ({
  useI18n: () => i18nMock,
  I18nT: {
    template: '<div><slot name="key" /><slot name="env" /></div>',
  },
}))

function setReducedMotion(matches: boolean) {
  Object.defineProperty(window, 'matchMedia', {
    value: vi.fn().mockImplementation((query: string) => ({
      matches,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
    configurable: true,
  })
}

function createControlledStream() {
  const encoder = new TextEncoder()
  let controller!: ReadableStreamDefaultController<Uint8Array>
  const stream = new ReadableStream<Uint8Array>({
    start(ctrl) {
      controller = ctrl
    },
  })
  return {
    stream,
    enqueue: (text: string) => controller.enqueue(encoder.encode(text)),
    close: () => controller.close(),
  }
}

async function flushStream() {
  await new Promise((resolve) => setTimeout(resolve, 0))
  await nextTick()
}

async function openAssistant() {
  const wrapper = mount(AiAssistant)
  await flushPromises()
  await wrapper.find('.ai-fab').trigger('click')
  await nextTick()
  return wrapper
}

describe('AiAssistant', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.stubGlobal('fetch', fetchMock)
    apiMock.get.mockResolvedValue({ data: { available: true } })
    setReducedMotion(false)
  })

  it('renders typing dots until the first streamed chunk and appends text progressively', async () => {
    const controlled = createControlledStream()
    fetchMock.mockResolvedValue({
      ok: true,
      body: controlled.stream,
    })
    const wrapper = await openAssistant()

    await wrapper.find('textarea').setValue('How do I check locks?')
    await wrapper.find('.ai-send').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="ai-assistant-typing"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="ai-typing-dots"]').exists()).toBe(true)

    controlled.enqueue('data: Check \n\n')
    await flushStream()

    expect(wrapper.find('[data-testid="ai-assistant-typing"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('Check')

    controlled.enqueue('data: pg_locks.\n\ndata: [DONE]\n\n')
    controlled.close()
    await flushStream()

    expect(wrapper.text()).toContain('Check pg_locks.')
    expect(apiMock.post).not.toHaveBeenCalled()
  })

  it('renders a static typing fallback when reduced motion is preferred', async () => {
    setReducedMotion(true)
    fetchMock.mockReturnValue(new Promise(() => {}))
    const wrapper = await openAssistant()

    await wrapper.find('textarea').setValue('How do I check locks?')
    await wrapper.find('.ai-send').trigger('click')
    await nextTick()

    expect(wrapper.find('[data-testid="ai-assistant-typing"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="ai-typing-dots"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('AI is thinking')
  })

  it('falls back to the non-streaming assistant endpoint when streaming fails', async () => {
    fetchMock.mockRejectedValue(new Error('stream unavailable'))
    apiMock.post.mockResolvedValue({ data: { answer: 'Fallback answer.' } })
    const wrapper = await openAssistant()

    await wrapper.find('textarea').setValue('How do I check locks?')
    await wrapper.find('.ai-send').trigger('click')
    await flushPromises()

    expect(apiMock.post).toHaveBeenCalledWith('/ai/assistant', {
      question: 'How do I check locks?',
      lang: 'en',
    })
    expect(wrapper.text()).toContain('Fallback answer.')
    expect(wrapper.find('[data-testid="ai-assistant-typing"]').exists()).toBe(false)
  })
})
