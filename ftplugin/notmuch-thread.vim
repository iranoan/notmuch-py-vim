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
	l:colorcolumn = 7
	l:n_colorcolumn = 7
	for l:i in g:notmuch_display_item[0 : 1]
		if l:i ==? 'subject'
			l:n_colorcolumn += g:notmuch_subject_length + 1
			l:colorcolumn ..= ',' .. l:n_colorcolumn
		elseif l:i ==? 'from'
			l:n_colorcolumn += g:notmuch_from_length + 1
			l:colorcolumn ..= ',' .. l:n_colorcolumn
		elseif l:i ==? 'date'
			l:n_colorcolumn += py3eval(len(datetime.datetime(2022, 10, 26, 23, 10, 10, 555555).strftime(date_format))) + 1
			" date_format によっては日付時刻が最も長くなりそうな 2022/10/26 23:10:10.555555 September, Wednesday
			l:colorcolumn ..= ',' .. l:n_colorcolumn
		endif
	endfor
	execute 'setlocal colorcolumn=' .. l:colorcolumn
	if g:notmuch_visible_line == 2
		execute 'highlight ColorColumn ' .. substitute(notmuch_py#Get_highlight('Normal'), '\m\C\%(bg\|fg\)\ze\=', '\={"bg": "fg", "fg": "bg"}[submatch(0)]', 'g')
	endif
endfunction

setlocal statusline=%<%{(line('$')==1&&getline('$')==#'')?'\ \ \ -/-\ \ \ ':printf('%4d/%-4d',line('.'),line('$'))}\ tag:\ %{b:notmuch.tags}%=%4{line('w$')*100/line('$')}%%
sign define notmuch text=* texthl=notmuchMark
if exists('g:notmuch_visible_line') && type('g:notmuch_visible_line') == 0 && ( g:notmuch_visible_line == 1 || g:notmuch_visible_line == 2 )
	setlocal nomodifiable tabstop=1 cursorline nowrap nonumber signcolumn=yes foldmethod=expr foldminlines=1 foldcolumn=0 foldtext=notmuch_py#FoldThreadText() foldlevel=0 concealcursor=nv conceallevel=3 nolist
	SetColorcolmun()
elseif has('patch-8.2.2518')
	setlocal nomodifiable tabstop=1 cursorline nowrap nonumber signcolumn=yes foldmethod=expr foldminlines=1 foldcolumn=0 foldtext=notmuch_py#FoldThreadText() foldlevel=0 concealcursor=nv conceallevel=3 list listchars=tab:\|\   # 他は非表示
else
	setlocal nomodifiable tabstop=1 cursorline nowrap nonumber signcolumn=yes foldmethod=expr foldminlines=1 foldcolumn=0 foldtext=notmuch_py#FoldThreadText() foldlevel=0 concealcursor=nv conceallevel=3 nolist
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
	b:undo_ftplugin ..= '| setlocal concealcursor< conceallevel< cursorline< foldcolumn< foldexpr< foldlevel< foldlevel< foldmethod< foldminlines< foldtext< list< listchars< modifiable< number< signcolumn< tabstop< wrap< modifiable< buftype< bufhidden< equalalways< fileencoding< swapfile<'
else
	b:undo_ftplugin = 'setlocal concealcursor< conceallevel< cursorline< foldcolumn< foldexpr< foldlevel< foldlevel< foldmethod< foldminlines< foldtext< list< listchars< modifiable< number< signcolumn< tabstop< wrap< modifiable< buftype< bufhidden< equalalways< fileencoding< swapfile<'
endif
