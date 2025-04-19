vim9script
# Author:  Iranoan <iranoan+vim@gmail.com>
# License: GPL Ver.3.

scriptencoding utf-8

if exists('b:did_ftplugin_plugin')
	finish
endif
b:did_ftplugin_plugin = 1

if !exists('g:ft_notmuch_thread')
	g:ft_notmuch_thread = 1
	augroup NotmuchThreadType
		autocmd!
		if has('patch-8.2.2518')
			autocmd BufWinEnter,WinNew * if &filetype ==# 'notmuch-thread' | setlocal list foldlevel=0 | endif
		else
			autocmd BufWinEnter,WinNew * if &filetype ==# 'notmuch-thread' | setlocal nolist foldlevel=0 | endif
		endif
	augroup END
endif

function SetColorcolmun() abort
	let l:colorcolumn = 7
	let l:n_colorcolumn = 7
	for l:i in g:notmuch_display_item[0 : 1]
		if l:i ==? 'subject'
			let l:n_colorcolumn += g:notmuch_subject_length + 1
			let l:colorcolumn ..= ',' .. l:n_colorcolumn
		elseif l:i ==? 'from'
			let l:n_colorcolumn += g:notmuch_from_length + 1
			let l:colorcolumn ..= ',' .. l:n_colorcolumn
		elseif l:i ==? 'date'
			let l:n_colorcolumn += py3eval(len(datetime.datetime(2022, 10, 26, 23, 10, 10, 555555).strftime(date_format))) + 1
			" date_format によっては日付時刻が最も長くなりそうな 2022/10/26 23:10:10.555555 September, Wednesday
			let l:colorcolumn ..= ',' .. l:n_colorcolumn
		endif
	endfor
	execute 'setlocal colorcolumn=' .. l:colorcolumn
	if g:notmuch_visible_line == 2
		execute 'highlight ColorColumn ' .. substitute(notmuch_py#Get_highlight('Normal'), '\m\C\%(bg\|fg\)\ze\=', '\={"bg": "fg", "fg": "bg"}[submatch(0)]', 'g')
	endif
endfunction

setlocal statusline=%<%{(line('$')==1&&getline('$')==#'')?'\ \ \ -/-\ \ \ ':printf('%4d/%-4d',line('.'),line('$'))}\ tag:\ %{b:notmuch.tags}%=%4{line('w$')*100/line('$')}%%
sign define notmuch text=* texthl=notmuchMark
setlocal nomodifiable tabstop=1 cursorline nowrap nonumber signcolumn=yes foldmethod=expr foldminlines=1 foldcolumn=0 foldtext=notmuch_py#FoldThreadText() foldlevel=0 concealcursor=nvc conceallevel=3 nolist
var bar_w: bool = false
if &ambiwidth ==# 'double'
	bar_w = true
	setlocal concealcursor-=v
	setlocal concealcursor-=c
endif
for i in getcellwidths()
	if i[0] >= 0x2502 && i[1] <= 0x2502
		if i[2] == 2
			bar_w = true
		else
			bar_w = false
		endif
		break
	endif
endfor
if exists('g:notmuch_visible_line') && type(g:notmuch_visible_line) == 0
	if g:notmuch_visible_line == 1 || g:notmuch_visible_line == 2
		SetColorcolmun()
	elseif g:notmuch_visible_line == 3
		setlocal conceallevel=1
		if bar_w == true
			setlocal concealcursor-=v
			setlocal concealcursor-=c
		else
			setlocal concealcursor+=v
			setlocal concealcursor+=c
		endif
	endif
elseif has('patch-8.2.2518')
	if bar_w
		setlocal list listchars=tab:\|\   # 他は非表示
	else
		setlocal list listchars=tab:│\   # 他は非表示
	endif
endif
if exists('g:notmuch_display_item')
	execute 'setlocal foldexpr=notmuch_py#FoldThread(' .. index(g:notmuch_display_item, 'Subject', 0, v:true) .. ')'
else
	setlocal foldexpr=notmuch_py#FoldThread(0)
endif

# keymap
nnoremap <buffer><silent>a :Notmuch tag-add<CR>
vnoremap <buffer><silent>a :Notmuch tag-add<CR>
nnoremap <buffer><silent>A :Notmuch tag-delete<CR>
vnoremap <buffer><silent>A :Notmuch tag-delete<CR>
nnoremap <buffer><silent>C :Notmuch thread-connect<CR>
nnoremap <buffer><silent>d :Notmuch tag-set +Trash -unread<CR>:Notmuch thread-next<CR>
vnoremap <buffer><silent>d :Notmuch tag-set +Trash -unread<CR>:Notmuch thread-next<CR>
nnoremap <buffer><silent>D :Notmuch attach-delete<CR>
vnoremap <buffer><silent>D :Notmuch attach-delete<CR>
nnoremap <buffer><silent>o :Notmuch thread-toggle<CR>
nnoremap <buffer><silent>O :Notmuch open<CR>
nnoremap <buffer><silent>s :Notmuch search<CR>
nnoremap <buffer><silent>S :Notmuch mail-save<CR>
nnoremap <buffer><silent>u :Notmuch tag-toggle unread<CR>:Notmuch thread-next<CR>
vnoremap <buffer><silent>u :Notmuch tag-toggle unread<CR>:Notmuch thread-next<CR>
nnoremap <buffer><silent>zn <Nop>


if exists('b:undo_ftplugin')
	b:undo_ftplugin ..= '| call undoftplgin#Thread()'
else
	b:undo_ftplugin = 'call undoftplgin#Thread()'
endif
