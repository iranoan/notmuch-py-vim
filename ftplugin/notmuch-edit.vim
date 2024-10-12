vim9script
# Author:  Iranoan <iranoan+vim@gmail.com>
# License: GPL Ver.3.

scriptencoding utf-8

if !exists('w:did_ftplugin_plugin') || !w:did_ftplugin_plugin
	setlocal signcolumn=auto foldmethod=syntax foldlevel=1 nomodeline
	w:did_ftplugin_plugin = 1
endif

if exists('b:did_ftplugin_plugin')
	finish
endif
b:did_ftplugin_plugin = 1

if exists('b:undo_ftplugin')
	b:undo_ftplugin ..= '| call undoftplgin#Edit()'
else
	b:undo_ftplugin = 'call undoftplgin#Edit()'
endif

execute 'source ' .. expand('<sfile>:p:h:h') .. '/macros/notmuch-edit.vim'
