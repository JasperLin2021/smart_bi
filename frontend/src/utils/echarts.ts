// ECharts 按需注册入口：全工程统一从这里 import，避免打包全量 echarts（~1MB）。
// 需要新增图型/组件时在这里注册即可。
import * as echarts from "echarts/core"
import {
  BarChart,
  FunnelChart,
  GaugeChart,
  LineChart,
  PieChart,
  ScatterChart,
} from "echarts/charts"
import {
  AxisPointerComponent,
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
} from "echarts/components"
import { CanvasRenderer } from "echarts/renderers"

echarts.use([
  BarChart,
  LineChart,
  PieChart,
  ScatterChart,
  GaugeChart,
  FunnelChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
  AxisPointerComponent,
  CanvasRenderer,
])

export * from "echarts/core"
