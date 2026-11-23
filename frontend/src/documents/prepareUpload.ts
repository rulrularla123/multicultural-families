import { ApiError } from '../api/client'

const MAX_BYTES = 10 * 1024 * 1024
const MAX_TEXT = 80_000
const WORD_NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
const PDF = 'application/pdf'
const DOCX = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'

// Keep these number formats in sync with backend/app/common/identity_patterns.py.
function maskIdentifiers(text: string): string {
  return text
    .replace(/(?<![0-9])[0-9]{6}\s?-?\s?[1-8][0-9]{6}(?![0-9])/g, '[등록번호 가림]')
    .replace(/(?<![A-Za-z0-9])[A-Za-z]{1,2}[0-9]{7,8}(?![A-Za-z0-9])/g, '[여권번호 가림]')
    .replace(/(?<![0-9])010[\s-]?[0-9]{4}[\s-]?[0-9]{4}(?![0-9])/g, '[전화번호 가림]')
}

async function readPdf(data: Uint8Array) {
  const [{ getDocument, GlobalWorkerOptions }, { default: workerUrl }] = await Promise.all([
    import('pdfjs-dist/legacy/build/pdf.mjs'),
    import('pdfjs-dist/legacy/build/pdf.worker.min.mjs?url'),
  ])
  GlobalWorkerOptions.workerSrc = workerUrl
  const task = getDocument({ data, useWasm: false, stopAtErrors: true })
  task.onPassword = () => { void task.destroy() }
  try {
    const pdf = await task.promise
    const pages: string[] = []
    let length = 0
    for (let number = 1; number <= pdf.numPages && length < MAX_TEXT; number++) {
      const page = await pdf.getPage(number)
      const content = await page.getTextContent()
      const pageText = content.items.map((item) => 'str' in item ? item.str + (item.hasEOL ? '\n' : '') : '').join('').trim()
      pages.push(pageText)
      length += pageText.length + 1
      page.cleanup()
    }
    return { text: pages.join('\f'), page_count: pdf.numPages }
  } finally {
    await task.destroy()
  }
}

function paragraphText(paragraph: Element): string {
  return Array.from(paragraph.getElementsByTagNameNS(WORD_NS, '*'), (node) => {
    switch (node.localName) {
      case 't': return node.textContent ?? ''
      case 'tab': return '\t'
      case 'br': return node.getAttributeNS(WORD_NS, 'type') === 'page' ? '\f' : '\n'
      default: return ''
    }
  }).join('')
}

async function readDocx(data: Uint8Array) {
  const { Uint8ArrayReader, ZipReader } = await import('@zip.js/zip.js')
  const zip = new ZipReader(new Uint8ArrayReader(data), { useWebWorkers: false })
  try {
    const entry = (await zip.getEntries()).find((item) => item.filename === 'word/document.xml')
    if (!entry || entry.directory || entry.uncompressedSize > MAX_BYTES) throw new ApiError(415, null)
    const decoder = new TextDecoder()
    const chunks: string[] = []
    let size = 0
    await entry.getData(new WritableStream<Uint8Array>({
      write(chunk) {
        size += chunk.byteLength
        if (size > MAX_BYTES) throw new ApiError(422, null)
        chunks.push(decoder.decode(chunk, { stream: true }))
      },
      close() { chunks.push(decoder.decode()) },
    }))
    const xml = new DOMParser().parseFromString(chunks.join(''), 'application/xml')
    const body = xml.getElementsByTagNameNS(WORD_NS, 'body')[0]
    if (!body || xml.getElementsByTagName('parsererror').length) throw new ApiError(415, null)
    const lines = Array.from(body.children).flatMap((node) => {
      if (node.namespaceURI !== WORD_NS) return []
      if (node.localName === 'p') return [paragraphText(node)]
      if (node.localName !== 'tbl') return []
      return Array.from(node.getElementsByTagNameNS(WORD_NS, 'tr'), (row) =>
        Array.from(row.children)
          .filter((cell) => cell.namespaceURI === WORD_NS && cell.localName === 'tc')
          .map((cell) => paragraphText(cell).trim())
          .join('\t'),
      )
    })
    const text = lines.join('\n')
    return { text, page_count: text.split('\f').length }
  } finally {
    await zip.close()
  }
}

export async function prepareUpload(file: File) {
  if (file.size > MAX_BYTES) throw new ApiError(413, null)
  const name = file.name.toLowerCase()
  const format = name.endsWith('.pdf') ? 'pdf' : name.endsWith('.docx') ? 'docx'
    : file.type === PDF ? 'pdf' : file.type === DOCX ? 'docx' : null
  if (!format) throw new ApiError(415, null)

  const bytes = new Uint8Array(await file.arrayBuffer())
  if (format === 'pdf' && new TextDecoder().decode(bytes.subarray(0, 5)) !== '%PDF-') {
    throw new ApiError(415, null)
  }
  try {
    const extracted = format === 'pdf' ? await readPdf(bytes) : await readDocx(bytes)
    // Mask before truncating so an identifier at the size boundary is covered.
    const text = maskIdentifiers(extracted.text).trim().slice(0, MAX_TEXT)
    if (text.replaceAll('\f', '').trim().length < 30) throw new ApiError(422, null)
    return { text, page_count: extracted.page_count, format, file_size: file.size }
  } catch (error) {
    if (error instanceof ApiError) throw error
    throw new ApiError(422, null)
  }
}
