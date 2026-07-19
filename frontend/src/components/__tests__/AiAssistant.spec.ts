import { flushPromises, mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import AiAssistant from '../AiAssistant.vue'

const apiMock = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
}))

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
    apiMock.get.mockResolvedValue({ data: { available: true } })
    setReducedMotion(false)
  })

  it('renders animated typing dots while waiting for an assistant response', async () => {
    let resolvePost!: (value: unknown) => void
    apiMock.post.mockReturnValue(new Promise((resolve) => {
      resolvePost = resolve
    }))
    const wrapper = await openAssistant()

    await wrapper.find('textarea').setValue('How do I check locks?')
    await wrapper.find('.ai-send').trigger('click')
    await nextTick()

    expect(wrapper.find('[data-testid="ai-assistant-typing"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="ai-typing-dots"]').exists()).toBe(true)

    resolvePost({ data: { answer: 'Check pg_locks.' } })
    await flushPromises()

    expect(wrapper.find('[data-testid="ai-assistant-typing"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('Check pg_locks.')
  })

  it('renders a static typing fallback when reduced motion is preferred', async () => {
    setReducedMotion(true)
    apiMock.post.mockReturnValue(new Promise(() => {}))
    const wrapper = await openAssistant()

    await wrapper.find('textarea').setValue('How do I check locks?')
    await wrapper.find('.ai-send').trigger('click')
    await nextTick()

    expect(wrapper.find('[data-testid="ai-assistant-typing"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="ai-typing-dots"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('AI is thinking')
  })
})
