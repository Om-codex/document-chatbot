/**
 * Tour B — Your Guide to Using the Document Chatbot.
 *
 * This tour describes the real interface in `chat.html` and the behaviour
 * implemented in `js/app.js`: the health pill, dropzone, paste-text dialog,
 * library selection, scope summary, top-k field, composer, cited answers,
 * error banner and toasts. It does not invent features.
 */

export const appTour = {
  id: "app",
  storageKey: "document-chatbot.tour.app",
  kicker: "App tour",
  title: "Your Guide to Using the Document Chatbot",
  subtitle:
    "Eight steps through the real interface — from your first upload to reading an answer with its sources.",
  intro:
    "This tour is a practical walkthrough of the app. Each step points at a real control, explains what it does, and shows what you should expect to see.",
  labels: {
    what: "What you see",
    why: "Why it helps",
    tech: "Where in the UI",
    input: "You provide",
    output: "You get",
    next: "Next",
  },
  steps: [
    {
      id: "open",
      kicker: "Step 1 of 8",
      title: "Open the app and check the connection",
      visual: "app-shell",
      summary:
        "The chatbot lives at /app/chat.html. The header shows the app name, a back link, a theme toggle and a live connection pill.",
      what:
        "While the page loads, the pill reads “Connecting…”. It then becomes “Connected” when the API and vector store are healthy, “Degraded” if the vector store cannot be read, or “API offline” if the backend cannot be reached. Hovering it shows the configured models, collection and document count.",
      why:
        "The pill tells you immediately whether a problem is in your browser or in the backend, so you do not debug an upload when the server is simply not running.",
      tech:
        "Top-right of the header. The theme toggle and the “← Back to site” link sit next to it.",
      input: "Open http://127.0.0.1:8000/app/chat.html with the FastAPI server running.",
      output: "A connected status pill and your existing document library.",
      next:
        "With a healthy connection, add your first document.",
    },
    {
      id: "upload",
      kicker: "Step 2 of 8",
      title: "Add documents or paste text",
      visual: "app-upload",
      summary:
        "The “Add documents” panel accepts PDF, TXT and DOCX files up to 10 MB each, up to 10 files at a time.",
      what:
        "Drop files onto the dashed area, press Enter on it, or use “Choose files”. A progress bar tracks the upload and a feedback list reports each file. “Paste text” opens a dialog with a title and content field for notes that are not in a file.",
      why:
        "Everything goes through the same ingestion pipeline, so pasted notes become searchable exactly like an uploaded file. Per-file feedback means one rejected file does not hide the success of the others.",
      tech:
        "Left sidebar, “Add documents” panel. Drag-and-drop and the hidden file input are wired to the same handler.",
      input: "One or more PDF, TXT or DOCX files, or pasted plain text.",
      output:
        "Indexed documents in the library, each with a chunk count. The response also returns the document's content-based ID.",
      next:
        "Check what landed in the library before asking questions.",
    },
    {
      id: "library",
      kicker: "Step 3 of 8",
      title: "Manage your document library",
      visual: "app-library",
      summary:
        "The “Library” panel lists every indexed document with its page and chunk counts, plus selection and delete controls.",
      what:
        "The count badge shows how many documents are indexed. Tick a document to include it in retrieval, use “Select all” to switch the whole library on or off, and use the refresh button to reload the list. The bin icon deletes a document and all of its chunks after a confirmation prompt.",
      why:
        "The library is the boundary of what the chatbot can know. Deleting a document removes its vectors, so it can no longer influence an answer.",
      tech:
        "Left sidebar, below the upload panel. Each row has a checkbox, a filename, a page/chunk summary and a delete button.",
      input: "Selection changes or a delete confirmation.",
      output: "An updated selection, or a document removed from Chroma and from disk.",
      next:
        "Your selection controls what the next question searches.",
    },
    {
      id: "scope",
      kicker: "Step 4 of 8",
      title: "Choose the scope and retrieval depth",
      visual: "app-scope",
      summary:
        "The chat header summarises the current scope, and the composer's “Sources” field sets how many chunks to retrieve.",
      what:
        "With nothing selected, the header reads “Searching all N documents”. Tick specific files and it changes to “Searching X of N documents”. The Sources field accepts a whole number from 1 to 20 and remembers your choice in this browser.",
      why:
        "Scoping narrows the search to the documents you trust for this question. Raising top-k gives the model more context; lowering it keeps the prompt focused and cheaper in tokens.",
      tech:
        "Scope summary at the top of the chat panel; Sources number field at the bottom-right of the composer.",
      input: "A document selection and a top-k value between 1 and 20.",
      output: "A scoped retrieval request for every question you ask next.",
      next:
        "Now ask a question about the selected documents.",
    },
    {
      id: "ask",
      kicker: "Step 5 of 8",
      title: "Ask a question in your own words",
      visual: "app-composer",
      summary:
        "Type into the composer and press Enter to send, or Shift+Enter for a new line. The Send button stays disabled until the app is ready.",
      what:
        "The field accepts up to 4,000 characters and shows a live counter. When documents exist, the empty chat offers example prompts such as “Summarize the key points”. “Clear chat” removes the conversation without touching your documents.",
      why:
        "A natural question works better than keywords because the retriever embeds the whole sentence. Clearing the chat is only cosmetic — it does not change the library or the index.",
      tech:
        "Composer at the bottom of the chat panel. The hint reads “Answers cite sources · Enter to send” when ready.",
      input: "A question of up to 4,000 characters.",
      output: "The question in the conversation and a “Searching your documents…” indicator.",
      next:
        "Read the answer, then open its sources.",
    },
    {
      id: "answer",
      kicker: "Step 6 of 8",
      title: "Read the answer and open its sources",
      visual: "app-answer",
      summary:
        "Answers appear in the conversation with an expandable “N sources” section underneath.",
      what:
        "Expand the sources to see each retrieved chunk with its filename, chunk index and page information when available, plus the passage text itself. If retrieval returns nothing, the app shows a deterministic message instead of calling the model.",
      why:
        "The sources are the evidence. Reading them lets you confirm that the answer is supported and that the retriever found the right part of the right document.",
      tech:
        "Conversation area in the centre. Sources render as a native expandable details element.",
      input: "The completed chat response.",
      output: "An answer, a source count, and the retrieved passages with metadata.",
      next:
        "If something goes wrong, the app reports it without an alert box.",
    },
    {
      id: "errors",
      kicker: "Step 7 of 8",
      title: "Recover from errors calmly",
      visual: "app-errors",
      summary:
        "Failures appear as a dismissible banner, inline feedback, or a toast — never a browser alert.",
      what:
        "Upload problems list the reason per file. A failed question shows a readable message in the conversation. Provider issues such as rate limits are translated into plain language, and the banner can be dismissed with its × button. Successful actions such as deleting a document appear as a short toast.",
      why:
        "Readable errors tell you what to change: retry later, pick another file, start the server, or reduce the scope. The interface keeps the rest of the session usable.",
      tech:
        "Banner at the bottom of the viewport; upload feedback inside the upload panel; toast near the bottom-right.",
      input: "A network failure, invalid file, provider error or empty retrieval.",
      output: "A specific message and, where possible, a way to retry.",
      next:
        "A few habits keep results reliable.",
    },
    {
      id: "tips",
      kicker: "Step 8 of 8",
      title: "Good habits and where to go next",
      visual: "app-tips",
      summary:
        "Grounded does not mean infallible. Treat answers as a fast first pass and verify anything important against the cited passage.",
      what:
        "Ask specific questions, scope to the relevant document, and keep top-k modest unless the answer needs more context. Re-uploading identical content replaces the existing document rather than duplicating it. Add ?mock=1 to the chat URL to preview the interface without a backend.",
      why:
        "Retrieval quality depends on chunking, the question and the source material. Checking the sources catches the cases where the right-sounding answer came from the wrong passage.",
      tech:
        "Replay this tour from the site navigation or the About page at any time. Your completion is remembered locally.",
      input: "A few focused questions and a look at the cited passages.",
      output: "More reliable use of the tool — and a clear picture of its limits.",
      next:
        "Open the chatbot and try it, or explore the engine tour to see what happens behind each answer.",
    },
  ],
};
