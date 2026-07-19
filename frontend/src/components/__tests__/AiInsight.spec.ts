import { flushPromises, mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import AiInsight from '../AiInsight.vue'

const apiMock = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
}))

const i18nMock = vi.hoisted(() => ({
  locale: { value: 'en' },
  t: vi.fn((key: string) => {
    const map: Record<string, string> = {
      'ai.analyzing': 'AI is analyzing',
      'ai.disabledShort': 'AI disabled',
      'ai.requestError': 'AI request error',
      'ai.statusWarning': 'Warning',
      'ai.statusOk': 'OK',
      'ai.statusCritical': 'Critical',
      'ai.badgeDefault': 'AI analysis',
      'ai.copy': 'Copy',
      'ai.copySql': 'Copy SQL',
      'ai.downloadMd': 'Download .md',
      'ai.copied': 'Copied',
      'ai.copyFailed': 'Failed to copy',
      'ai.downloaded': 'File ready',
      'ai.exportBadge': 'Status',
      'ai.thinkingStatic': 'AI is thinking',
    }
    return map[key] || key
  }),
  tm: vi.fn((key: string) => {
    const map: Record<string, string[]> = {
      'ai.thinkingPhrases': ['Reading data', 'Analyzing', 'Preparing recommendations'],
    }
    return map[key] || []
  }),
}))

vi.mock('../../api/client', () => ({ default: apiMock }))
vi.mock('vue-i18n', () => ({ useI18n: () => i18nMock }))

function mountInsight() {
  return mount(AiInsight, {
    props: {
      label: 'Run advisor',
      endpoint: '/ai/test-advisor',
      payload: () => ({ payload: '{"settings":[]}' }),
      sections: [
        { key: 'findings', title: 'Findings' },
        { key: 'recommendations', title: 'Recommendations' },
      ],
      badgeField: 'severity',
    },
  })
}

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

describe('AiInsight', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    i18nMock.locale.value = 'en'
    apiMock.get.mockResolvedValue({ data: { available: true } })
    setReducedMotion(false)
  })

  it('renders run button and AI results from a successful post', async () => {
    apiMock.post.mockResolvedValue({
      data: {
        severity: 'warning',
        summary: 'Review memory settings',
        findings: ['work_mem is low'],
        recommendations: ['Consider SET work_mem = 16MB'],
      },
    })
    const wrapper = mountInsight()

    await flushPromises()
    expect(wrapper.find('button.ai-insight-btn').text()).toContain('Run advisor')

    await wrapper.find('button.ai-insight-btn').trigger('click')
    await flushPromises()

    expect(apiMock.post).toHaveBeenCalledWith('/ai/test-advisor', {
      payload: '{"settings":[]}',
      lang: 'en',
    })
    expect(wrapper.text()).toContain('Warning')
    expect(wrapper.text()).toContain('Review memory settings')
    expect(wrapper.text()).toContain('work_mem is low')
    expect(wrapper.text()).toContain('Consider SET work_mem = 16MB')
  })

  it('shows disabled hint when AI status is unavailable', async () => {
    apiMock.get.mockResolvedValue({ data: { available: false } })
    const wrapper = mountInsight()

    await flushPromises()

    expect(wrapper.find('button.ai-insight-btn').attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('AI disabled')
    expect(apiMock.post).not.toHaveBeenCalled()
  })

  it('posts the current locale with the request', async () => {
    i18nMock.locale.value = 'kk'
    apiMock.post.mockResolvedValue({
      data: {
        severity: 'ok',
        summary: 'Жақсы',
        findings: [],
        recommendations: [],
      },
    })
    const wrapper = mountInsight()

    await flushPromises()
    await wrapper.find('button.ai-insight-btn').trigger('click')
    await flushPromises()

    expect(apiMock.post).toHaveBeenCalledWith('/ai/test-advisor', {
      payload: '{"settings":[]}',
      lang: 'kk',
    })
  })

  it('exports rendered markdown and SQL-like recommendations', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText },
      configurable: true,
    })
    apiMock.post.mockResolvedValue({
      data: {
        severity: 'warning',
        summary: 'Review query plan',
        findings: ['Seq scan on orders'],
        recommendations: ['CREATE INDEX idx_orders_customer_id ON orders(customer_id);'],
      },
    })
    const wrapper = mountInsight()

    await flushPromises()
    await wrapper.find('button.ai-insight-btn').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="ai-copy"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="ai-copy-sql"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="ai-download"]').exists()).toBe(true)

    await wrapper.find('[data-testid="ai-copy"]').trigger('click')
    await flushPromises()
    expect(writeText).toHaveBeenLastCalledWith(expect.stringContaining('# Run advisor'))
    expect(writeText).toHaveBeenLastCalledWith(expect.stringContaining('Review query plan'))

    await wrapper.find('[data-testid="ai-copy-sql"]').trigger('click')
    await flushPromises()
    expect(writeText).toHaveBeenLastCalledWith('CREATE INDEX idx_orders_customer_id ON orders(customer_id);')
    expect(wrapper.text()).toContain('Copied')
  })

  it('renders animated thinking loader while loading and removes it after result arrives', async () => {
    let resolvePost!: (value: unknown) => void
    apiMock.post.mockReturnValue(new Promise((resolve) => {
      resolvePost = resolve
    }))
    const wrapper = mountInsight()

    await flushPromises()
    await wrapper.find('button.ai-insight-btn').trigger('click')
    await nextTick()

    expect(wrapper.find('[data-testid="ai-thinking-loader"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="ai-thinking-shimmer"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Reading data')

    resolvePost({
      data: {
        severity: 'ok',
        summary: 'Looks good',
        findings: [],
        recommendations: [],
      },
    })
    await flushPromises()

    expect(wrapper.find('[data-testid="ai-thinking-loader"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('Looks good')
  })

  it('uses a static loading label when reduced motion is preferred', async () => {
    setReducedMotion(true)
    apiMock.post.mockReturnValue(new Promise(() => {}))
    const wrapper = mountInsight()

    await flushPromises()
    await wrapper.find('button.ai-insight-btn').trigger('click')
    await nextTick()

    expect(wrapper.find('[data-testid="ai-thinking-loader"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="ai-thinking-shimmer"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('AI is thinking')
  })
})
