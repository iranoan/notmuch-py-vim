vim9script
scriptencoding utf-8

export def Notmuch(): void # folders, thread, show 共通
	mapclear <buffer>
	setlocal expandtab< autoindent< smartindent< cindent< indentexpr< formatoptions< comments< foldtext<
	unlet! b:did_ftplugin_plugin
enddef

export def EditDraft(): void
	mapclear <buffer>
	setlocal expandtab< autoindent< smartindent< indentexpr< formatoptions< comments< foldtext<
enddef

export def Edit(): void
	setlocal foldmethod< modeline< signcolumn<
	unlet! b:did_ftplugin_plugin
enddef

export def Draft(): void
	mapclear <buffer>
	setlocal autoindent< cindent< comments< expandtab< foldtext< formatoptions< indentexpr< smartindent< foldcolumn< signcolumn< foldmethod<
	unlet! b:did_ftplugin_plugin
enddef

export def Thread(): void
	setlocal concealcursor< conceallevel< cursorline< foldcolumn< foldexpr< foldlevel< foldlevel< foldmethod< foldminlines< list< listchars< modifiable< number< signcolumn< tabstop< wrap< modifiable< buftype< bufhidden< equalalways< fileencoding< swapfile<
	Notmuch()
enddef

export def Folder(): void
	setlocal statusline< cursorline< wrap< winminwidth< list< signcolumn< number< foldcolumn< modifiable< buftype< bufhidden< equalalways< fileencoding< swapfile<
	Notmuch()
enddef

export def Show(): void
	setlocal concealcursor< conceallevel< foldcolumn< foldlevel< foldlevel< foldmethod< list< modifiable< number< signcolumn< modifiable< buftype< bufhidden< equalalways< fileencoding< swapfile<
	Notmuch()
enddef
