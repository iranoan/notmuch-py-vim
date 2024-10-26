vim9script
scriptencoding utf-8

export def Notmuch(): void # folders, thread, show 共通
	nunmap <buffer><F1>
	nunmap <buffer><leader>h
	nunmap <buffer><Leader>s
	nunmap <buffer><Tab>
	nunmap <buffer><S-Tab>
	nunmap <buffer><space>
	nunmap <buffer><BS>
	nunmap <buffer>J
	nunmap <buffer>P
	nunmap <buffer><C-R>
	nunmap <buffer>p
	nunmap <buffer>I
	nunmap <buffer>R
	nunmap <buffer>c
	nunmap <buffer>i
	nunmap <buffer>r
	setlocal expandtab< autoindent< smartindent< cindent< indentexpr< formatoptions< comments< foldtext<
	unlet! b:did_ftplugin_plugin
enddef

export def EditDraft(): void
	nunmap <buffer><leader>q
	setlocal expandtab< autoindent< smartindent< indentexpr< formatoptions< comments< foldtext<
enddef

export def Edit(): void
	setlocal foldmethod< modeline< signcolumn<
	unlet! b:did_ftplugin_plugin w:did_ftplugin_plugin
enddef

export def Draft(): void
	nunmap <buffer><Leader>s
	nunmap <buffer><leader>a
	nunmap <buffer><leader>t
	nunmap <buffer><leader>A
	nunmap <buffer><leader>d
	nunmap <buffer><leader>p
	nunmap <buffer><leader>f
	nunmap <buffer><leader>c
	nunmap <buffer><leader>e
	nunmap <buffer><leader>h
	nunmap <buffer><F1>
	setlocal autoindent< cindent< comments< expandtab< foldtext< formatoptions< indentexpr< smartindent< foldcolumn< signcolumn< foldmethod<
	unlet! b:did_ftplugin_plugin
enddef

export def Thread(): void
	nunmap <buffer>a
	vunmap <buffer>a
	nunmap <buffer>A
	vunmap <buffer>A
	nunmap <buffer>C
	nunmap <buffer>d
	vunmap <buffer>d
	nunmap <buffer>D
	vunmap <buffer>D
	nunmap <buffer>o
	nunmap <buffer>O
	nunmap <buffer>s
	nunmap <buffer>S
	nunmap <buffer>u
	vunmap <buffer>u
	nunmap <buffer>zn
	setlocal concealcursor< conceallevel< cursorline< foldcolumn< foldexpr< foldlevel< foldlevel< foldmethod< foldminlines< list< listchars< modifiable< number< signcolumn< tabstop< wrap< modifiable< buftype< bufhidden< equalalways< fileencoding< swapfile<
	Notmuch()
enddef

export def Folder(): void
	nunmap <buffer>o
	nunmap <buffer><2-LeftMouse>
	nunmap <buffer>s
	setlocal statusline< cursorline< wrap< winminwidth< list< signcolumn< number< foldcolumn< modifiable< buftype< bufhidden< equalalways< fileencoding< swapfile<
	Notmuch()
enddef

export def Show(): void
	nunmap <buffer>a
	nunmap <buffer>A
	nunmap <buffer>d
	nunmap <buffer>D
	vunmap <buffer>D
	nunmap <buffer>o
	vunmap <buffer>o
	nunmap <buffer><2-LeftMouse>
	nunmap <buffer>s
	vunmap <buffer>s
	nunmap <buffer>S
	nunmap <buffer>u
	nunmap <buffer>O
	nunmap <buffer>X
	setlocal concealcursor< conceallevel< foldcolumn< foldlevel< foldlevel< foldmethod< list< modifiable< number< signcolumn< modifiable< buftype< bufhidden< equalalways< fileencoding< swapfile<
	Notmuch()
enddef
