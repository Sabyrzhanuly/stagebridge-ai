import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import LangSwitcher from '../LangSwitcher.vue'

const setLangMock = vi.hoisted(() => vi.fn())

vi.mock('../../i18n', () => ({
  SUPPORTED_LANGS: ['ru', 'kk', 'en'],
  setLang: setLangMock,
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    locale: { value: 'ru' },
    t: (key: string) => key,
  }),
}))

describe('LangSwitcher', () => {
  beforeEach(() => {
    setLangMock.mockClear()
  })

  it('renders supported language codes', () => {
    const wrapper = mount(LangSwitcher)

    expect(wrapper.findAll('button').map((button) => button.text())).toEqual([
      'РУС',
      'ҚАЗ',
      'ENG',
    ])
  })

  it('calls setLang when a language is clicked', async () => {
    const wrapper = mount(LangSwitcher)

    await wrapper.findAll('button')[1].trigger('click')

    expect(setLangMock).toHaveBeenCalledWith('kk')
  })
})
