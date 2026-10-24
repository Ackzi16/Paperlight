"""English / Simplified Chinese UI strings. PDF contents never pass through here."""
from __future__ import annotations

import re
from PySide6.QtCore import QObject, Signal, QSettings, QTranslator, QLibraryInfo
from PySide6.QtWidgets import QApplication


STRINGS={
    'Rotate object':'旋转对象',
    'Rotate object…':'旋转对象…',
    'Angle in degrees':'角度',
    'Edit points':'编辑节点',
    'This path has too many points for direct editing.':'此路径的节点过多，无法直接编辑。',
    'Drag anchors or curve handles. Shift constrains movement. Escape cancels a gesture.':'拖动节点或曲线控制点。按住 Shift 限制移动方向，按 Escape 取消本次操作。',
    'Drag to move. Drag a corner to resize or the round handle above to rotate. Right-click for Edit points and an exact angle.':'拖动以移动，拖动角点以调整大小，拖动上方圆点以旋转。右键可编辑节点或输入精确角度。',
    'Edit preview timed out. Reading remains available.':'编辑预览超时，仍可阅读文档。',
    'The edit preview could not be prepared.':'无法生成编辑预览。',

    'Identical overlapping text cannot be edited separately.':'无法单独编辑位置相同的重叠文字。',
    'This shared graphic is too complex for text editing.':'此共享图形过于复杂，无法进行文字编辑。',
    'This shared graphic uses an unsupported resource name.':'此共享图形使用不支持的资源名称。',
    'This shared graphic has recursive resources.':'此共享图形包含递归资源，无法编辑。',

    'Move text box':'移动文本框',
    'This text box would overlap other text. Move or resize it first.':'此文本框会与其他文字重叠，请先移动或调整大小。',
    'Edit PDF':'编辑 PDF',
    'Resize':'调整大小',
    'Text box':'文本框',
    'Rectangle':'矩形',
    'Ellipse':'椭圆',
    'Line':'直线',
    'Graphic':'图形',
    'Image':'图像',
    'Recognized text':'已识别文字',
    'Edit text':'编辑文字',
    'Delete object':'删除对象',
    'Stroke color':'描边颜色',
    'Fill color':'填充颜色',
    'Click to select a text box, shape or image. Drag to move; drag a corner to resize. Double-click text to type. Only this page is analyzed.':'单击选择文本框、形状或图像，拖动以移动，拖动角点以调整大小。双击文字即可输入。仅分析当前页。',
    'Drag to move; drag a corner to resize. Right-click for appearance or Delete. Alt+click cycles overlapping objects.':'拖动以移动，拖动角点以调整大小。右键设置外观或删除。Alt+单击可切换重叠对象。',
    'Rotate this page upright before editing this text box.':'请先将此页旋转至正向，再编辑此文本框。',
    'Edit this text box directly. Resize changes wrapping. Three dots changes formatting. Ctrl+Enter applies; Escape cancels.':'直接编辑此文本框。调整大小会改变换行，三点按钮可设置格式。Ctrl+Enter 应用，Escape 取消。',
    'This page is too complex for object editing.':'此页过于复杂，无法进行对象编辑。',
    'This annotation type uses its original markup tool.':'请使用原有标注工具编辑此类型的批注。',
    'This graphic has clipping, shared resources or a complex content stream.':'此图形包含裁切、共享资源或复杂内容流，暂不支持直接编辑。',
    'The page changed. Select the object again.':'页面已更改，请重新选择对象。',
    'This object cannot be changed by the graphic editor.':'图形编辑器无法修改此对象。',
    'The object source could not be verified.':'无法验证对象源数据。',
    'Invalid object dimensions.':'对象尺寸无效。',
    'Invalid object color.':'对象颜色无效。',
    'Invalid stroke width.':'描边宽度无效。',
    'This object has a singular transform.':'此对象的变换不可逆，无法编辑。',
    'Overlapping text needs a smaller correction area.':'存在重叠文字，请缩小修改区域。',
    'The text does not fit. Resize the text box or reduce the font size.':'文字无法放入，请调整文本框大小或减小字号。',
    'Apply or undo pending redactions before editing text.':'请先应用或撤销待处理的隐去标记，再编辑文字。',
    'Invalid recognition page range.':'识别页码范围无效。',

    'More tools':'更多工具',
    'Edit':'编辑',
    'Text formatting':'文本格式',
    'Done':'完成',
    'Font':'字体',
    'Size':'字号',
    'Drag text to select; drag blank space to pan.':'拖动文字以选择，拖动空白处以平移。',
    'Click to create a text box. Type on the page; use the three dots to format.':'单击创建文本框，在页面上输入，点击三点按钮调整格式。',
    'Click farther from the page edge to add text.':'请在离页面边缘稍远的位置单击以添加文本。',
    'Type on the page. Three dots: formatting. Done or Ctrl+Enter: apply. Escape: cancel.':'在页面上输入。三点按钮：格式；完成或 Ctrl+Enter：应用；Escape：取消。',
    'OCR is selectable for reading. Unlock editing to add the text layer to this PDF.':'OCR 文字可供选择和阅读。请解锁编辑以向 PDF 添加文字层。',
    'No new scan text found. Existing text remains selectable; unreadable scans may need another OCR pass.':'未找到新的扫描文字。现有 PDF 文字已可选择。',
    'OCR text added. Select or copy it, or use Correct text to replace scan text. Save to keep the text layer.':'已添加 OCR 文字。可以选择、复制，或使用“更正文字”替换扫描文字。保存以保留文字层。',
    'No interactive field here. Choose Add text and click on the page to type.':'此处没有交互表单字段。请选择“添加文字”并单击页面输入。',

    'Invalid recognition data. The worker was stopped.':'识别数据无效，已停止识别进程。',
    'Old search caches could not be removed. Clear local search cache before processing sensitive documents.':'无法移除旧搜索缓存。处理敏感文档前，请先清除本地搜索缓存。',
    'Session-only by default. Enable to reuse encrypted indexes between sessions. Password-protected PDFs always use session-only indexes.':'默认仅在当前会话保留。启用后可跨会话复用加密索引。受密码保护的 PDF 始终仅使用会话索引。',
    'This document exceeds the supported file size.':'此文档超过支持的文件大小。',
    'This document exceeds the supported page count.':'此文档超过支持的页数。',
    'This document contains unsupported page dimensions.':'此文档包含不支持的页面尺寸。',
    'This document contains an image exceeding the supported size.':'此文档包含超过支持大小的图像。',
    'Saved signatures could not be protected. Review the signature library before use.':'无法保护已存签名。使用前请检查签名库。',
    'Remember encrypted search cache':'跨会话保留加密搜索缓存',
    'Recognition timed out. Completed pages remain available.':'文字识别超时。已完成的页面仍可使用。',
    'Redaction verification failed. The edit was cancelled because text remains in the marked area.':'隐去验证失败：标记区域内仍有文本，已取消此编辑。',
    'Save':'保存',
    'Save changes to this document before continuing?':'是否先将更改保存到当前文档，再继续？',
    'Saved changes to the current document.':'更改已保存到当前文档。',
    'The original PDF changed outside Paperlight. Reopen it or use Save copy to keep your edits separately.':'原 PDF 已在 Paperlight 之外被更改。请重新打开文档，或使用“另存副本”单独保留当前编辑。',
    'Choose either existing protection or new protection.':'请选择保留原有保护或设置新的保护。',
    'Fit width':'适合宽度',
    'Save current drawing as signature…':'将当前笔迹保存为签名…',
    '&View':'视图(&V)', 'Single page':'单页显示', 'Continuous scroll':'连续滚动',
    'Saved signature':'已存签名', 'Saved signatures':'已存签名',
    'Create / manage signatures…':'创建／管理签名…',
    "Drag a box to place your saved signature. Today's date is added if selected.":'拖出矩形框以放置签名。如已勾选，将同时添加当天日期。',
    'Draw with your mouse, then save for reuse or place it in this PDF.':'使用鼠标绘制签名，然后保存以供重复使用，或放入当前 PDF。',
    'New signature':'新建签名', 'Delete signature':'删除签名',
    'Signature name':'签名名称', 'Clear drawing':'清除笔迹', 'Save signature':'保存签名',
    "Include today's date":'附上当天日期', 'Date format':'日期格式', 'Date at placement':'放置时的日期',
    'Saved signatures are encrypted for your Windows account. This is a visual signature, not a certificate-based digital signature.':'签名已使用当前 Windows 账户加密保存在本机。这是外观签名，不是基于证书的数字签名。',
    'Place signature':'放置签名', 'New unsaved signature':'新建未保存的签名',
    'Signature saved on this computer.':'签名已保存在本机。',
    'Draw a signature before saving or placing it.':'请先绘制签名，再保存或放置。',
    'Give this signature a name.':'请为此签名命名。',
    'The saved signature library could not be read.':'无法读取已保存的签名库。',
    'Draw a larger box for the signature.':'请为签名绘制更大的矩形框。',
    'Inserted PDF password (owner password if editing is restricted)':'待插入 PDF 的密码（若限制编辑，请输入所有者密码）',
    'Read-only':'只读', 'Save without protection?':'不加保护地保存？',
    'Save copy creates an unencrypted PDF. Use File > Protect PDF to set passwords and editing restrictions.':'“另存副本”会生成未加密的 PDF。如需设置密码和编辑权限，请使用“文件 > 保护 PDF”。',
    'Protect PDF…':'保护 PDF…', 'Protect PDF':'保护 PDF',
    'Unlock editing…':'解锁编辑…', 'Unlock editing':'解锁编辑',
    'Save protected copy':'保存受保护副本',
    'Require a password to open the document':'打开文档时需要密码',
    'Opening password':'打开密码', 'Confirm opening password':'确认打开密码',
    'Owner password for editing':'用于编辑的所有者密码', 'Confirm owner password':'确认所有者密码',
    'Allow printing':'允许打印', 'Allow copying text and images':'允许复制文本和图像',
    'Show passwords':'显示密码',
    'Save a separate PDF with AES-256 encryption. Keep the owner password to unlock editing.':'使用 AES-256 加密另存 PDF。请保管好所有者密码，以便解锁编辑。',
    'Editing, form filling and page changes will be restricted. Some PDF tools can bypass permissions. An opening password protects contents before access; it cannot prevent screenshots or OCR after opening. Passwords cannot be recovered by Paperlight. Use long, unique passwords.':'将限制编辑、填写表单和更改页面。部分 PDF 工具可以绕过权限限制。打开密码可保护未解锁文档的内容，但无法阻止打开后的截图或文字识别。Paperlight 无法找回密码。请使用较长且不重复的密码。',
    'Enter an owner password to control editing.':'请输入用于控制编辑权限的所有者密码。',
    'Passwords must contain at most 40 UTF-8 bytes and no null characters.':'密码的 UTF-8 编码不能超过 40 字节，且不能包含空字符。',
    'Use different opening and owner passwords.':'请为打开文档和所有者权限设置不同的密码。',
    'Owner passwords do not match.':'两次输入的所有者密码不一致。',
    'Opening passwords do not match.':'两次输入的打开密码不一致。',
    'Enter an opening password or turn off the opening password requirement.':'请输入打开密码，或关闭打开文档时需要密码的选项。',
    'Protected PDF verification failed.':'受保护 PDF 验证失败。',
    'Unlock editing with the owner password first.':'请先使用所有者密码解锁编辑。',
    'Incorrect owner password.':'所有者密码不正确。',
    'Read-only PDF. Use File > Unlock editing with the owner password.':'此 PDF 为只读。请通过“文件 > 解锁编辑”输入所有者密码。',
    'Protected copy saved. The current editing session remains unlocked.':'受保护副本已保存。当前编辑会话仍处于解锁状态。',
    'Editing unlocked. Save copy exports without protection; Protect PDF creates a protected copy.':'编辑已解锁。“另存副本”会导出不受保护的副本；“保护 PDF”可创建受保护副本。',
    'Document':'文档',
    '&File':'文件(&F)', '&Edit':'编辑(&E)', '&Pages':'页面(&P)', '&Tools':'工具(&T)', '&Help':'帮助(&H)',
    'Open PDF':'打开 PDF', 'Save copy':'另存副本', 'Export searchable copy':'导出可搜索副本',
    'Undo':'撤销', 'Redo':'重做', 'Copy selected text':'复制所选文本',
    'Select all text on page':'选择本页全部文本', 'Clear text selection':'取消文本选择',
    'Show or hide sidebar':'显示或隐藏侧边栏', 'PDF workspace':'PDF 工作区',
    'Recognize text':'识别文本', 'Stop OCR':'停止识别', 'Clear local search cache':'清除本地搜索缓存',
    'Find':'查找', 'Previous page · Alt+Left':'上一页 · Alt+Left',
    'Next page · Alt+Right':'下一页 · Alt+Right', 'Go to page':'跳转到页面',
    'Zoom out':'缩小', 'Zoom in':'放大', 'Fit page':'适合页面', 'Markup':'标注',
    'Read':'阅读', 'Select text':'选择文本', 'Draw / sign':'绘制／签名',
    'Add text':'添加文本', 'Correct text':'修改文本', 'Signature image':'签名图片',
    'Fill form':'填写表单', 'Redact':'涂黑隐去', 'Ink color':'画笔颜色', 'Stroke width':'线条粗细',
    'Apply redactions':'应用隐去', 'Rotate right':'向右旋转', 'Move page earlier':'向前移动页面',
    'Move page later':'向后移动页面', 'Delete selected pages':'删除所选页面',
    'Extract / split pages':'提取／拆分页面', 'Insert / merge PDF':'插入／合并 PDF',
    'Quick guide':'使用指南', 'About Paperlight':'关于 Paperlight',
    'Thumbnails':'缩略图', 'Search':'搜索', 'Find text in this PDF':'在此 PDF 中查找文本',
    'Open a PDF to search.':'打开 PDF 后即可搜索。',
    'Read, mark up, organize and search PDFs.\nEnglish and Chinese OCR works offline.':'阅读、标注、整理和搜索 PDF。\n支持离线中英文文字识别。',
    'Open a PDF':'打开 PDF', 'or drop a PDF here':'或将 PDF 拖放到此处',
    'Open a PDF to get started':'打开 PDF 即可开始', 'On your computer  ·  Offline':'本机处理  ·  离线',
    'Match the document':'匹配文档样式', 'Selected text style':'所选文本样式',
    'Most frequently used document style':'文档中最常用的样式',
    'No native font metadata · standard font fallback':'没有原始字体信息 · 使用标准替代字体',
    '  ·  most used':'  ·  最常用', '  ·  default':'  ·  默认',
    'Color':'颜色', 'Alignment':'对齐方式', 'Left':'左对齐', 'Center':'居中', 'Right':'右对齐',
    'Line spacing':'行距', 'Apply text':'应用文本', 'Text color':'文本颜色',
    'Place text':'放置文本', 'Embedded PDF font':'PDF 内嵌字体', 'Standard PDF font':'PDF 标准字体',
    'Installed copy of PDF font':'本机安装的同名字体', 'fallback for missing glyphs':'缺失字符使用替代字形',
    'Original font unavailable':'原字体不可用', 'readable substitute':'使用可读的替代字体',
    '. Font choice, size, color and spacing apply to this text box.':'。字体、字号、颜色和行距将应用于此文本框。',
    'Unsaved changes':'尚未保存的更改', 'Save an edited copy before continuing?':'是否先保存编辑后的副本，再继续？',
    'PDF documents (*.pdf)':'PDF 文档 (*.pdf)', 'Images (*.png *.jpg *.jpeg *.bmp *.webp)':'图片 (*.png *.jpg *.jpeg *.bmp *.webp)',
    'Password':'密码', 'PDF password':'PDF 密码', 'Inserted PDF password':'待插入 PDF 的密码',
    'Choose signature image':'选择签名图片', 'Form field':'表单字段',
    'Read with the hand tool. Choose a markup tool to edit.':'使用手形工具浏览，选择标注工具进行编辑。',
    'Drag to pan. Use the page arrows or thumbnails to navigate.':'拖动可平移，使用翻页箭头或缩略图跳转页面。',
    'Drag across text to select. Ctrl+C copies. Double-click selects a word. Ctrl+A selects this page.':'拖动选择文本，Ctrl+C 复制，双击选择单词，Ctrl+A 选择本页全部文本。',
    'Draw with the mouse. Use this tool for a handwritten signature.':'使用鼠标绘制，也可用此工具手写签名。',
    'Drag a box where you want to type.':'在需要输入的位置拖出一个文本框。',
    'Drag a box around the word or paragraph to replace. Scan pixels inside it will be removed.':'框选要替换的词语或段落。框内的扫描图像像素也会被移除。',
    'Drag a box for the signature image.':'拖出一个区域以放置签名图片。',
    'Click an existing form field. Use Add text for a paper form.':'点击现有表单字段。对于纸质表单，请使用“添加文本”。',
    'Drag over sensitive content, then choose Apply redactions.':'框选敏感内容，然后选择“应用隐去”。',
    'No selectable text on this page. Choose Recognize text to read a scan.':'本页没有可选择的文本。对于扫描件，请先选择“识别文本”。',
    'Drag across text to select. Ctrl+C copies. Double-click selects a word.':'拖动选择文本，Ctrl+C 复制，双击选择单词。',
    'Redaction marked. Apply redactions before saving, or Undo to remove the mark.':'已标记隐去区域。保存前请应用隐去，或撤销以移除标记。',
    'Certificate signatures are not supported. Use Draw / sign or Signature image.':'暂不支持证书签名。请使用“绘制／签名”或“签名图片”。',
    'This button type is not supported by the field editor. Use Add text if needed.':'表单编辑器暂不支持此按钮类型。需要时可使用“添加文本”。',
    'No interactive field here. Choose Add text and draw a box to type on this page.':'此处没有交互式表单字段。请选择“添加文本”，并拖出文本框后输入。',
    'Remove annotation':'移除批注', 'Remove this annotation?':'是否移除此批注？', 'Delete pages':'删除页面',
    'Pages to save in a separate PDF, such as 1-5, 9, 12-20':'输入要另存为独立 PDF 的页码，例如 1-5, 9, 12-20',
    'Save extracted pages':'保存提取的页面', 'Insert PDF after current page':'在当前页之后插入 PDF',
    'Apply permanent redactions':'应用永久隐去',
    'Remove the marked text, image pixels, intersecting form fields and annotations?\n\nSaved files cannot recover removed content. Save updates the current file; Save copy preserves the original. Undo remains available only in this editing session.':'是否移除标记区域内的文本、图像像素，以及与之相交的表单字段和批注？\n\n保存后的文件无法恢复已移除的内容。“保存”会更新当前文件；“另存副本”会保留原文件。仅在当前编辑会话中可以撤销。',
    'Redactions applied. Save the document or a copy to write the sanitized PDF.':'已应用隐去。请保存当前文档或另存副本，生成移除敏感内容后的 PDF。',
    'Save edited copy':'保存编辑后的副本', 'OCR is incomplete':'文字识别尚未完成',
    'Export searchable PDF':'导出可搜索 PDF',
    'Document changed. Choose Recognize text to refresh OCR and search.':'文档已更改。请选择“识别文本”，以更新识别结果和搜索索引。',
    'Reading searchable text…':'正在读取可搜索文本…', 'Indexing text, then recognizing scanned pages…':'正在建立文本索引，随后识别扫描页面…',
    'Reading text. Results will appear as pages become available.':'正在读取文本。各页就绪后将陆续显示搜索结果。',
    'OCR process could not run. You can keep reading and editing.':'无法启动文字识别进程。您仍可继续阅读和编辑。',
    'Recognition stopped unexpectedly. Text indexed so far is available.':'识别意外停止。已建立索引的文本仍可使用。',
    'Recognition stopped. Pages indexed so far remain searchable.':'识别已停止。已完成索引的页面仍可搜索。',
    'Local search cache cleared. Documents are unchanged.':'已清除本地搜索缓存。文档未更改。',
    ' · OCR still running':' · 仍在识别文本', ' · some scans need OCR':' · 部分扫描页仍需识别',
    'Enter pages such as 1-3, 7, 10-12.':'请输入页码，例如 1-3, 7, 10-12。',
    'Page ranges must run forwards.':'页码范围必须从小到大。', 'Invalid page range.':'页码范围无效。',
    'Saved page count does not match the document.':'保存后的页数与原文档不一致。',
    'This PDF needs the correct password.':'请输入此 PDF 的正确密码。',
    'Open a PDF containing at least one page.':'请打开至少包含一页的 PDF。',
    'A page order must contain each page exactly once.':'页面顺序中每一页必须且只能出现一次。',
    'Keep at least one page in the document.':'文档中至少需要保留一页。',
    'The inserted PDF needs its password.':'待插入的 PDF 需要密码。',
    'Apply or undo pending redactions before correcting text.':'修改文本前，请先应用或撤销尚未处理的隐去标记。',
    'This form field is read-only.':'此表单字段为只读。',
    'Choose a different filename to preserve the original PDF.':'请选择不同的文件名，以保留原始 PDF。',
    'Choose a new filename. Paperlight preserves the original PDF.':'请选择新文件名。Paperlight 会保留原始 PDF。',
    'Apply or undo the pending redactions before saving.':'保存前，请先应用或撤销尚未处理的隐去标记。',
    'Apply or undo pending redactions before saving.':'保存前，请先应用或撤销尚未处理的隐去标记。',
    'Apply or undo your marked redactions before saving.':'保存前，请先应用或撤销已标记的隐去区域。',
    'Apply or undo pending redactions before exporting.':'导出前，请先应用或撤销尚未处理的隐去标记。',
    'Apply or undo pending redactions before extracting pages.':'提取页面前，请先应用或撤销尚未处理的隐去标记。',
    'The text does not fit. Widen the box or reduce the font size.':'文本无法完整放入此框。请加宽文本框或减小字号。',
    'The text does not fit in the selected rectangle.':'文本无法完整放入所选区域。',
    'The text does not fit. Enlarge the box or reduce the font size.':'文本无法完整放入此框。请扩大文本框或减小字号。',
    'Could not start the OCR process.':'无法启动文字识别进程。',
    'Save':'保存', 'Cancel':'取消', 'Discard':'放弃', 'Yes':'是', 'No':'否', 'OK':'确定', 'Apply':'应用',
}

TEMPLATES={
    '{0}. Font choice, size, color and spacing apply to this text box.':'{0}。字体、字号、颜色和行距将应用于此文本框。',
    'Page {0}':'第 {0} 页', 'Page {0} of {1}':'第 {0} 页，共 {1} 页',
    'Page {0}\n{1}':'第 {0} 页\n{1}',
    '{0} characters selected · Ctrl+C to copy':'已选择 {0} 个字符 · Ctrl+C 复制',
    'Copied {0} characters':'已复制 {0} 个字符',
    'Delete {0} selected page(s)? You can undo this change.':'是否删除所选的 {0} 页？此更改可以撤销。',
    'Extracted {0} pages to {1}':'已提取 {0} 页，保存为 {1}',
    'Saved {0}. Original preserved.':'已保存 {0}。原始文件已保留。',
    'Exported searchable copy: {0}':'已导出可搜索副本：{0}',
    '{0} pages have not completed OCR. Export the recognized pages so far?':'还有 {0} 页尚未完成文字识别。是否先导出已识别的页面？',
    'Text available from {0} pages. {1} may need OCR.':'已读取 {0} 页文本，其中 {1} 页可能需要文字识别。',
    'Recognizing page {0} · {1} of {2} scanned pages':'正在识别第 {0} 页 · 扫描页进度 {1}/{2}',
    'OCR could not read page {0}. Other pages will continue.':'无法识别第 {0} 页，将继续处理其他页面。',
    'OCR stopped: {0}':'文字识别已停止：{0}',
    'OCR finished with {0} unreadable pages. Retry Recognize text if needed.':'文字识别已结束，有 {0} 页无法识别。需要时可再次选择“识别文本”。',
    'Text indexed · {0} pages may need OCR. Choose Recognize text.':'已建立文本索引 · {0} 页可能需要文字识别。请选择“识别文本”。',
    'Search ready · {0} pages · {1}s · local index cached':'搜索已就绪 · {0} 页 · {1} 秒 · 已缓存本地索引',
    '{0} pages indexed. Choose Recognize text to read scans.':'已为 {0} 页建立索引。扫描页请选择“识别文本”。',
    '{0} pages indexed, including recognized scans.':'已为 {0} 页建立索引，包含已识别的扫描页。',
    '{0} matches in {1} indexed pages{2}':'在已索引的 {1} 页中找到 {0} 处匹配{2}',
    'Pages must be between 1 and {0}.':'页码必须介于 1 和 {0} 之间。',
}

GUIDE_EN=(
    'OPEN & READ\nOpen or drop a PDF. Use thumbnails or Alt+Left / Alt+Right. Ctrl+wheel zooms; Ctrl+0 fits the page.\n\n'
    'SELECT TEXT\nThe read cursor selects text automatically. Drag across text, double-click a word, '
    'or Ctrl+A for the current page. Ctrl+C copies; Escape clears. Recognize text first for scans.\n\n'
    'SEARCH\nCtrl+F finds existing text immediately. Recognize text runs English + Simplified/Traditional Chinese OCR offline. '
    'The first OCR pass takes time. Search caches are encrypted and session-only by default; Tools can enable reuse between sessions. Stop OCR preserves completed pages. '
    'Recognize text adds a selectable text layer to the current PDF. Save to keep it; Correct text replaces scan text.\n\n'
    'EDIT\nDraw / sign writes with your mouse. Click with Add text to type live on the page. Use the three-dot button to format, Done or Ctrl+Enter to apply, and Escape to cancel. All editing tools are visible on the toolbar. Drag a rectangle with Correct text to edit it on the page. '
    'Correct text removes the original contents inside that rectangle; it does not reflow surrounding paragraphs. '
    'Signature image places a PNG/JPEG in a rectangle. Fill form edits existing text, checkbox and choice fields. '
    'Right-click an annotation to remove it. Ctrl+Z / Ctrl+Y undo and redo.\n\n'
    'PAGES\nDrag thumbnails to reorder, or use Pages menu commands. Ctrl/Shift selects multiple thumbnails. '
    'Extract / split saves the chosen range separately. Insert / merge adds a PDF after the current page.\n\n'
    'REDACT & SAVE\nMark areas, then Apply redactions. Ctrl+S saves the current document; Save copy preserves the original. Redacted exports discard unused objects and metadata. '
    'Search caches for the current session are removed when redactions or corrections are applied. '
    'Tools > Clear local search cache removes all cached OCR text.\n\n'
    'OCR accuracy depends on scan quality. Existing cryptographic signatures are not preserved by editing. '
    'Save preserves existing password protection. Use File > Protect PDF to create a copy with new protection. Save copy creates an unencrypted edited copy after owner unlock.')
STRINGS[GUIDE_EN]=(
    '打开与阅读\n打开 PDF 或将其拖入窗口。使用缩略图或 Alt+Left / Alt+Right 翻页。Ctrl+滚轮缩放，Ctrl+0 适合页面。\n\n'
    '选择文本\n阅读光标会自动选择文本。拖动选择文本，双击选择单词，Ctrl+A 选择本页。Ctrl+C 复制，Esc 取消选择。扫描件请先识别文本。\n\n'
    '搜索\nCtrl+F 可立即搜索已有文本。“识别文本”支持离线英语、简体中文和繁体中文 OCR。首次识别需要时间。搜索缓存已加密，默认仅在当前会话保留；可通过“工具”启用跨会话复用。停止识别会保留已完成的页面。“识别文本”会向当前 PDF 添加可选择的文字层，保存即可保留。使用“更正文字”替换扫描文字。\n\n'
    '编辑\n“绘制／签名”支持鼠标书写。使用“添加文字”单击页面即可实时输入，三点按钮设置格式，完成或 Ctrl+Enter 应用，Escape 取消。所有编辑工具均显示在工具栏中。使用“更正文字”拖出区域即可就地编辑。修改文本会移除框内原有内容，不会重排周围段落。“签名图片”可放置 PNG/JPEG。“填写表单”支持文本、复选框和选项字段。右键点击批注可移除，Ctrl+Z / Ctrl+Y 撤销或重做。\n\n'
    '页面\n拖动缩略图可调整顺序，也可使用“页面”菜单。按住 Ctrl/Shift 可多选。“提取／拆分”将指定页面另存为 PDF。“插入／合并”在当前页后插入另一个 PDF。\n\n'
    '隐去与保存\n标记敏感区域后，选择“应用隐去”。Ctrl+S 保存当前文档；另存副本会保留原文件。隐去后的导出文件将移除无用对象和元数据。应用隐去或修改文本时，会清除当前会话对应的搜索缓存。“工具 > 清除本地搜索缓存”可移除全部识别缓存。\n\n'
    '识别准确率取决于扫描质量。编辑不会保留原有的证书签名。“保存”会保留原有密码保护。可通过“文件 > 保护 PDF”创建使用新保护设置的副本。所有者解锁后，“另存副本”会生成不加密的编辑副本。')

ABOUT_EN=('Paperlight 1.0.0\nAn offline PDF workspace for Windows.\n\n'
          'Built with PySide6 / Qt, PyMuPDF / MuPDF, and Tesseract. '
          'This source project is distributed under AGPL-3.0-or-later. '
          'Third-party notices are included with the application.\n\n'
          'Preview workflow references: Apple documentation. REA diagnostics were run on Windows; no Mac Preview binary was inspected.')
STRINGS[ABOUT_EN]=('Paperlight 1.0.0\n适用于 Windows 的离线 PDF 工作区。\n\n'
                  '使用 PySide6 / Qt、PyMuPDF / MuPDF 和 Tesseract 构建。项目源代码以 AGPL-3.0-or-later 许可发布，应用中附有第三方声明。\n\n'
                  'Preview 工作流参考 Apple 官方文档。已在 Windows 上运行 REA 诊断，未检查 Mac Preview 的二进制程序。')


def _pattern(template):
    pieces=re.split(r'(\{\d+\})',template)
    seen=set()
    regex=''
    for part in pieces:
        if re.fullmatch(r'\{\d+\}',part):
            name='p'+part[1:-1]
            regex+=f'(?P={name})' if name in seen else f'(?P<{name}>.*?)'
            seen.add(name)
        else:
            regex+=re.escape(part)
    return re.compile(regex,re.S)


_reverse={v:k for k,v in STRINGS.items()}
_patterns=[(_pattern(en),_pattern(zh),en,zh) for en,zh in sorted(TEMPLATES.items(),key=lambda pair:-len(re.sub(r'\{\d+\}','',pair[0])))]
_language='en'
_qt_translator=None


def t(text,language=None):
    if not isinstance(text,str):
        return text
    language=language or _language
    original=_reverse.get(text,text)
    if language=='zh_CN' and original in STRINGS:
        return STRINGS[original]
    if language=='en' and text in _reverse:
        return original
    for en_pattern,zh_pattern,en,zh in _patterns:
        match=(en_pattern if language=='zh_CN' else zh_pattern).fullmatch(text)
        if match:
            values={int(key[1:]):value for key,value in match.groupdict().items()}
            args=[values.get(n,'') for n in range(max(values,default=-1)+1)]
            # A status suffix is also UI text. Other captured values, including
            # filenames, search snippets and PDF text, are inserted unchanged.
            if en=='{0} matches in {1} indexed pages{2}':
                args[2]=t(args[2],language)
            if en=='{0}. Font choice, size, color and spacing apply to this text box.':
                args[0]=t(args[0],language)
            return (zh if language=='zh_CN' else en).format(*args)
    if ' · ' in text:
        return ' · '.join(t(part,language) for part in text.split(' · '))
    return original


def activate(language):
    global _language,_qt_translator
    _language=language
    app=QApplication.instance()
    if app is not None:
        from .theme import interface_style
        from PySide6.QtGui import QFont
        font = QFont('Microsoft YaHei UI' if language=='zh_CN' else 'Segoe UI')
        font.setPointSizeF(9.75 if language=='zh_CN' else 9)
        font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        app.setFont(font)
        app.setStyleSheet(interface_style(language))
        if _qt_translator is not None:
            app.removeTranslator(_qt_translator)
            _qt_translator=None
        if language=='zh_CN':
            translator=QTranslator(app)
            if translator.load('qtbase_zh_CN',QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
                app.installTranslator(translator)
                _qt_translator=translator


class LanguageManager(QObject):
    changed=Signal(str)

    def __init__(self,settings=None):
        super().__init__()
        self.settings=settings if settings is not None else QSettings('Paperlight','Paperlight')
        self.current=str(self.settings.value('interface/language','en'))
        if self.current not in ('en','zh_CN'):
            self.current='en'

    def set_language(self,language):
        if language not in ('en','zh_CN'):
            raise ValueError('Unsupported interface language')
        self.current=language
        self.settings.setValue('interface/language',language)
        self.settings.sync()
        activate(language)
        self.changed.emit(language)
