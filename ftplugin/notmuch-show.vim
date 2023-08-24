vim9script
# Author:  Iranoan <iranoan+vim@gmail.com>
# License: GPL Ver.3.

scriptencoding utf-8

if exists('b:did_ftplugin_plugin')
	finish
endif
b:did_ftplugin_plugin = 1

if !exists('g:ft_notmuch_show')
	g:ft_notmuch_show = 1
	augroup NotmuchShowType
		autocmd!
		autocmd BufWinEnter,WinEnter,WinNew * if &filetype ==# 'notmuch-show' |
					\ setlocal concealcursor=nvic conceallevel=3 nolist|
					\ 	call matchadd('Conceal', '\m[\x0C]') |
					\ 	call matchadd('Conceal', '\m[\u200B]') |
					\ endif
		autocmd BufWinEnter,WinNew * if &filetype ==# 'notmuch-show' |
					\ 	setlocal foldlevel=2 |
					\ endif
	augroup END
endif

if &statusline ==? ''
	setlocal statusline=%{%printf(printf("%%.%dS",&columns-53-strdisplaywidth(b:notmuch.date)),b:notmuch.subject)%}%=\ %{b:notmuch.date}\ %c:%v\ %3l/%L\ %3{line('w$')*100/line('$')}%%\ 0x%B
endif
setlocal tabstop=1 nomodifiable signcolumn=auto expandtab nonumber comments=n:> foldmethod=syntax foldtext=notmuch_py#FoldHeaderText() foldlevel=2 nolist
if &foldcolumn == 0
	setlocal foldcolumn=1
endif

def SwitchConceal(): void
	var lv: number
	lv = &conceallevel
	if lv != 0
		setlocal conceallevel=0
	else
		setlocal conceallevel=3
	endif
enddef

def ViewURL(): void
	var line_str: string = getline('.')
	var url: string
	var start: number
	var end = 0
	var urls: list<string>
	while 1
		[url, start, end] = matchstrpos(line_str, ']([^)]\+)', end)
		if start == -1
			break
		endif
		[url, start, start] = matchstrpos(url, '\v<(((https?|ftp|gopher)://|(mailto|file|news):)[^'' \t<>"]+|(www|web|w3)[a-z0-9_-]*\.[a-z0-9._-]+\.[^'' \t<>"]+)[a-z0-9/]|(\~?/)?([-A-Za-z._0-9]+/)*[-A-Za-z._0-9]+(\.\a([A-Za-z0-9]{,3})|/)', 1)
		if start == -1
			continue
		endif
		if count(urls, url) == 0
			call add(urls, url)
		endif
	endwhile
	urls = sort(urls, 'l')
	if len(urls) != 0
		if has('popupwin')
			call popup_atcursor(map(urls, '" " .. v:val'),
				{border: [1, 1, 1, 1],
					borderchars: ['─', '│', '─', '│', '┌', '┐', '┘', '└'],
					drag: 1,
					close: 'click',
					moved: 'any',
					col: 'cursor',
					'filter': "notmuch_py#Close_popup",
					wrap: 1,
					mapping: 0})
		else
			echo join(urls, "\n")
		endif
	endif
	return
enddef

# keymap
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
nnoremap <buffer><silent>O <Cmd>call <SID>SwitchConceal()<CR>
nnoremap <buffer><silent>P <Cmd>call <SID>ViewURL()<CR>
