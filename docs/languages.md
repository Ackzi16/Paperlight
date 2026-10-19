# Interface languages, version 0.4

Help now contains Language / 语言 with English and 简体中文. The interface switches live and retains the open document, current page, edits, selection and active tool. QSettings stores the choice under the Paperlight user's interface/language preference. Startup restores it without a restart prompt.

The catalog translates app menus/actions, tooltips, sidebar labels, page counts, editing dialogs, font-source notices, search/OCR progress, app-defined validation errors and the built-in guide. Qt's bundled Simplified Chinese translation supplies standard dialog buttons. Native file-picker system controls follow Windows itself; app-provided dialog titles and filters are translated.

PDF text, field values, search excerpts, clipboard text, filenames and actual font names are preserved. Translation templates insert dynamic values without translating them. Native language names remain visible in both languages so users can always find their way back.

Four added tests cover static/dynamic translation, unchanged document values, live Help-menu switching with unsaved edits and a selection, preference persistence, Chinese startup, text-editor localization, standard Qt buttons, and catalog coverage of marked static UI strings. The complete suite has 24 passing tests. English and Chinese are interface choices; OCR still supports English, Simplified Chinese and Traditional Chinese independently.
