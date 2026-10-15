// The cartesian build of Plotly ships without type declarations. The few
// functions used are typed where they are called, in components/chart.tsx.
declare module "plotly.js-cartesian-dist-min" {
  const Plotly: unknown
  export default Plotly
}
