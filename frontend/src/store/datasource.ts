import { defineStore } from "pinia"
import axios from "axios"

export interface DataSourceItem {
  id: number
  name: string
  slug: string
  is_active: number
  source_type?: string
}

export const useDatasourceStore = defineStore("datasource", {
  state: () => ({
    datasources: [] as DataSourceItem[],
    currentId: null as number | null,
  }),
  getters: {
    current(): DataSourceItem | undefined {
      return this.datasources.find(ds => ds.id === this.currentId)
    },
  },
  actions: {
    async fetchDatasources() {
      const response = await axios.get("/api/datasources")
      this.datasources = response.data
      // Auto-select first if no current selection
      if (!this.currentId && this.datasources.length > 0) {
        this.currentId = this.datasources.find(ds => ds.source_type === "excel")?.id || this.datasources[0].id
      }
    },
    switchDatasource(id: number) {
      this.currentId = id
    },
  },
})
