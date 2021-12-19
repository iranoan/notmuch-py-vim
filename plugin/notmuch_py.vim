" Author:  Iranoan <iranoan+vim@gmail.com>
" License: GPL Ver.3.

scriptencoding utf-8

let s:save_cpo = &cpoptions
set cpoptions&vim

if !has('python3') || v:version < 800
	echohl ErrorMsg | echomsg 'Require '+python3' and 'Ver.8.00 or later'.' | echohl None
	finish
endif

if has('nvim')
	echohl ErrorMsg | echomsg 'The plugin don''t work with NeoVim.' | echohl None
	finish
endif

if exists('g:loaded_notmuch_py')
	finish
endif
let g:loaded_notmuch_py = 1

let g:notmuch_command = { 'start': ['s:start_notmuch', 0], 'mail-new': ['s:new_mail', 1] }

command -range -nargs=* -complete=customlist,Notmuch_complete Notmuch call notmuch_py#notmuch_main(<line1>, <line2>, <f-args>)

" Reset User condition
let &cpoptions = s:save_cpo
unlet s:save_cpo
