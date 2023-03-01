" Author:  Iranoan <iranoan+vim@gmail.com>
" License: GPL Ver.3.

scriptencoding utf-8
scriptversion 4

if !exists('w:did_ftplugin_plugin') || !w:did_ftplugin_plugin
	setlocal signcolumn=auto foldmethod=syntax foldlevel=1
	let w:did_ftplugin_plugin = 1
endif

if exists('b:did_ftplugin_plugin')
	finish
endif
let b:did_ftplugin_plugin = 1

" if !exists('g:ft_notmuch_edit')
" 	let g:ft_notmuch_edit = 1
" endif

execute 'source ' .. expand('<sfile>:p:h:h') .. '/macros/notmuch-edit.vim'
