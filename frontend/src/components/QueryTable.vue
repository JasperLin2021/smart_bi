<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span class="card-header-title">查询结果</span>
        <div class="card-header-actions">
          <el-button size="small" @click="exportCsv">导出 CSV</el-button>
          <el-button size="small" @click="exportExcel">导出 Excel</el-button>
          <el-button size="small" @click="exportPng">导出 PNG</el-button>
          <el-button size="small" @click="exportPdf">导出 PDF</el-button>
        </div>
      </div>
    </template>
    <el-input
      v-if="rows.length"
      v-model="keyword"
      placeholder="筛选关键词"
      clearable
      class="table-toolbar"
    />
    <el-table
      v-if="rows.length"
      :data="pagedRows"
      border
      height="320"
    >
      <el-table-column
        v-for="column in columns"
        :key="column"
        :prop="column"
        :label="column"
        sortable
      />
    </el-table>
    <el-pagination
      v-if="rows.length"
      v-model:current-page="currentPage"
      v-model:page-size="pageSize"
      :total="filteredRows.length"
      layout="total, prev, pager, next, sizes"
      :page-sizes="[10, 20, 50]"
      class="table-pagination"
    />
    <el-empty v-else description="暂无数据"></el-empty>
  </el-card>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue"
import { saveAs } from "file-saver"
import * as XLSX from "xlsx"
import html2canvas from "html2canvas"
import jsPDF from "jspdf"

const props = defineProps<{
  columns: string[]
  rows: Array<Record<string, string | number>>
}>()

const rows = computed(() => props.rows)
const columns = computed(() => props.columns)
const keyword = ref("")
const currentPage = ref(1)
const pageSize = ref(10)

const filteredRows = computed(() => {
  if (!keyword.value.trim()) {
    return rows.value
  }
  const term = keyword.value.trim().toLowerCase()
  return rows.value.filter((row) =>
    Object.values(row).some((value) =>
      String(value).toLowerCase().includes(term)
    )
  )
})

const pagedRows = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filteredRows.value.slice(start, start + pageSize.value)
})

watch([rows, keyword], () => {
  currentPage.value = 1
})

const exportCsv = () => {
  if (!rows.value.length) return
  const worksheet = XLSX.utils.json_to_sheet(filteredRows.value)
  const csv = XLSX.utils.sheet_to_csv(worksheet)
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" })
  saveAs(blob, "query_result.csv")
}

const exportExcel = () => {
  if (!rows.value.length) return
  const worksheet = XLSX.utils.json_to_sheet(filteredRows.value)
  const workbook = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(workbook, worksheet, "Result")
  const buffer = XLSX.write(workbook, { type: "array", bookType: "xlsx" })
  const blob = new Blob([buffer], { type: "application/octet-stream" })
  saveAs(blob, "query_result.xlsx")
}

const exportPng = async () => {
  const tableElement = document.querySelector(".el-table") as HTMLElement | null
  if (!tableElement) return
  const canvas = await html2canvas(tableElement)
  canvas.toBlob((blob) => {
    if (blob) {
      saveAs(blob, "query_result.png")
    }
  })
}

const exportPdf = async () => {
  const tableElement = document.querySelector(".el-table") as HTMLElement | null
  if (!tableElement) return
  const canvas = await html2canvas(tableElement)
  const imageData = canvas.toDataURL("image/png")
  const pdf = new jsPDF("p", "pt", "a4")
  const pageWidth = pdf.internal.pageSize.getWidth()
  const pageHeight = (canvas.height * pageWidth) / canvas.width
  pdf.addImage(imageData, "PNG", 0, 0, pageWidth, pageHeight)
  pdf.save("query_result.pdf")
}
</script>
