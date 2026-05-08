<template>
  <div ref="editorRoot" class="sql-editor-wrap"></div>
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, watch } from "vue"
import { EditorView, keymap, lineNumbers, highlightActiveLine } from "@codemirror/view"
import { EditorState, Compartment } from "@codemirror/state"
import { sql, SQLite } from "@codemirror/lang-sql"
import { autocompletion, closeBrackets } from "@codemirror/autocomplete"
import { defaultKeymap, historyKeymap, history, indentWithTab } from "@codemirror/commands"
import { oneDark } from "@codemirror/theme-one-dark"
import axios from "axios"

const props = defineProps<{
  modelValue: string
  datasourceId?: number | null
  rows?: number
}>()

const emit = defineEmits<{
  "update:modelValue": [value: string]
}>()

const editorRoot = ref<HTMLElement | null>(null)
let view: EditorView | null = null
const schemaCompartment = new Compartment()

const buildSqlExtension = (schema: Record<string, string[]> = {}) =>
  sql({ dialect: SQLite, schema, upperCaseKeywords: true })

const fetchSchema = async (datasourceId: number) => {
  try {
    const token = localStorage.getItem("smart-bi-token")
    const res = await axios.get(`/api/datasources/${datasourceId}/schema-simple`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    const map: Record<string, string[]> = {}
    for (const t of res.data.tables ?? []) {
      map[t.name] = t.columns
    }
    return map
  } catch {
    return {}
  }
}

const initEditor = async () => {
  if (!editorRoot.value) return

  const schema = props.datasourceId ? await fetchSchema(props.datasourceId) : {}
  const minHeight = `${(props.rows ?? 6) * 21}px`

  view = new EditorView({
    state: EditorState.create({
      doc: props.modelValue ?? "",
      extensions: [
        history(),
        lineNumbers(),
        highlightActiveLine(),
        closeBrackets(),
        autocompletion(),
        schemaCompartment.of(buildSqlExtension(schema)),
        oneDark,
        keymap.of([indentWithTab, ...defaultKeymap, ...historyKeymap]),
        EditorView.updateListener.of((update) => {
          if (update.docChanged) {
            emit("update:modelValue", update.state.doc.toString())
          }
        }),
        EditorView.theme({
          "&": { fontSize: "13px", borderRadius: "6px", overflow: "hidden" },
          ".cm-scroller": { minHeight, fontFamily: "ui-monospace, Menlo, monospace" },
          ".cm-content": { padding: "8px 0" },
        }),
      ],
    }),
    parent: editorRoot.value,
  })
}

// Update schema when datasource changes
watch(() => props.datasourceId, async (id) => {
  if (!view || !id) return
  const schema = await fetchSchema(id)
  view.dispatch({ effects: schemaCompartment.reconfigure(buildSqlExtension(schema)) })
})

// Sync external model value changes (e.g. template apply)
watch(() => props.modelValue, (newVal) => {
  if (!view) return
  const current = view.state.doc.toString()
  if (current !== newVal) {
    view.dispatch({
      changes: { from: 0, to: current.length, insert: newVal ?? "" },
    })
  }
})

onMounted(() => { initEditor() })
onBeforeUnmount(() => { view?.destroy() })
</script>

<style scoped>
.sql-editor-wrap {
  border: 1px solid var(--app-border, #e5e7eb);
  border-radius: 6px;
  overflow: hidden;
  width: 100%;
}

.sql-editor-wrap :deep(.cm-editor.cm-focused) {
  outline: 2px solid rgba(15, 118, 110, 0.4);
  outline-offset: -1px;
}
</style>
