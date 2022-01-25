" Author:  Iranoan <iranoan+vim@gmail.com>
" License: GPL Ver.3.

scriptencoding utf-8

if exists('b:did_ftplugin_user')
	finish
endif
let b:did_ftplugin_user = 1

" if !exists('g:ft_notmuch_edit')
" 	let g:ft_notmuch_edit = 1
" endif

execute 'source ' . expand('<sfile>:p:h:h') . '/macros/notmuch-edit.vim'
