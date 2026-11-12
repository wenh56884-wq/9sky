// E1 多租户品牌化：租户只提供一个主色，其余色阶由 theme.js 推导
// 运维可在运行期通过 window.__JTW_BRAND__ 覆盖（不需要重新构建）
export const brand = {
  name: '九天梧桐',
  logo: '',          // 空 = 使用默认「梧」圆形 Logo
  primary: '#2f52e0', // ← 换租户只改这一个色值
}
