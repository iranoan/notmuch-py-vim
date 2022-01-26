" Author:  Iranoan <iranoan+vim@gmail.com>
" License: GPL Ver.3.

scriptencoding utf-8

if exists('b:did_ftplugin_user')
	finish
endif
let b:did_ftplugin_user = 1

" if !exists('g:ft_notmuch_show')
" 	let g:ft_notmuch_thread = 1
" endif

if &statusline !=? ''
	let s:status = substitute(&statusline, '"', '''', 'g')
	let s:status = substitute(s:status, '%[ymrhwq<]\c', '', 'g')
	let s:status = substitute(s:status, ' \[%{(&fenc!=''''?&fenc:&enc)}:%{ff_table\[&ff\]}\]', '', 'g')
	let s:status = substitute(s:status, '%f\c', '%{b:notmuch.subject}%= %<%{b:notmuch.date}', 'g')
	let s:status = substitute(s:status, ' \+', '\\ ', 'g')
	execute 'setlocal statusline='. s:status
else
	setlocal statusline=%{b:notmuch.subject}%=\ %<%{b:notmuch.date}\ %c:%v\ %3l/%L\ %3{line('w$')*100/line('$')}%%\ 0x%B
endif
setlocal tabstop=1 nomodifiable signcolumn=auto expandtab nonumber comments=n:> foldmethod=syntax foldlevel=2 foldtext=FoldHeaderText()
if &foldcolumn == 0
	setlocal foldcolumn=1
endif

setlocal concealcursor+=nvic conceallevel=3
call matchadd('Conceal', '[\x0C]')
call matchadd('Conceal', '[\u200B]')

" keymap
nnoremap <buffer><silent>a :Notmuch tag-add<CR>
nnoremap <buffer><silent>A :Notmuch tag-delete<CR>
nnoremap <buffer><silent>d :Notmuch tag-set +Trash -unread<CR>
nnoremap <buffer><silent>D :Notmuch attach-delete<CR>
vnoremap <buffer><silent>D :Notmuch attach-delete<CR>
nnoremap <buffer><silent>o :Notmuch open<CR>
vnoremap <buffer><silent>o :Notmuch open<CR>
nnoremap <2-LeftMouse>     :Notmuch open<CR>
nnoremap <buffer><silent>s :Notmuch attach-save<CR>
vnoremap <buffer><silent>s :Notmuch attach-save<CR>
nnoremap <buffer><silent>S :Notmuch mail-save<CR>
nnoremap <buffer><silent>u :Notmuch tag-toggle unread<CR>
