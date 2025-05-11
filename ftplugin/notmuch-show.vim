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
		autocmd BufWinEnter,WinEnter,WinNew * if &filetype ==# 'notmuch-show'
					| setlocal concealcursor=nvic conceallevel=3 nolist
					| 	matchadd('Conceal', '\m[\x0C]')
					| 	matchadd('Conceal', '\m[\u200B]')
					| endif
		autocmd BufWinEnter,WinNew * if &filetype ==# 'notmuch-show'
					| 	setlocal foldlevel=2
					| endif

	def SwitchConceal(): void
		if &conceallevel != 0
			setlocal conceallevel=0
		else
			setlocal conceallevel=3
		endif
		setlocal conceallevel?
	enddef

	def ViewURL(): void
		var line_str: string = getline('.')
		var url: string
		var m_start: number
		var m_end = 0
		var urls: list<string>
		while 1
			[url, m_start, m_end] = matchstrpos(line_str, ']([^)]\+)', m_end)
			if m_start == -1
				break
			endif
			[url, m_start, m_start] = matchstrpos(url, '\v<(((https?|ftp|gopher)://|(mailto|file|news):)[^'' \t<>"]+|(www|web|w3)[a-z0-9_-]*\.[a-z0-9._-]+\.[^'' \t<>"]+)[a-z0-9/]|(\~?/)?([-A-Za-z._0-9]+/)*[-A-Za-z._0-9]+(\.\a([A-Za-z0-9]{,3})|/)', 1)
			if m_start == -1
				continue
			endif
			if index(urls, url) == -1
				add(urls, url)
			endif
		endwhile
		urls = sort(urls, 'l')
		if len(urls) != 0
			if has('popupwin')
				popup_atcursor(map(urls, '" " .. v:val'),
					{border: [1, 1, 1, 1],
						borderchars: ['─', '│', '─', '│', '┌', '┐', '┘', '└'],
						drag: 1,
						close: 'click',
						moved: 'any',
						col: 'cursor',
						filter: "notmuch_py#Close_popup",
						wrap: 1,
						mapping: 0})
			else
				echo join(urls, "\n")
			endif
		endif
		return
	enddef

	augroup END
endif

if &statusline ==? ''
	setlocal statusline=%{%printf(printf("%%.%dS",&columns-53-strdisplaywidth(b:notmuch.date)),substitute(b:notmuch.subject,'%','%%','g'))%}%=\ %{b:notmuch.date}\ %c:%v\ %3l/%-3L\ %3{line('w$')*100/line('$')}%%\ 0x%B
endif
setlocal nomodifiable signcolumn=auto expandtab nonumber comments=n:> foldmethod=syntax foldtext=notmuch_py#FoldHeaderText() foldlevel=2 nolist
if &foldcolumn == 0
	setlocal foldcolumn=1
endif

# keymap
nnoremap <buffer><silent>a     <Cmd>Notmuch tag-add<CR>
nnoremap <buffer><silent>A     <Cmd>Notmuch tag-delete<CR>
nnoremap <buffer><silent>d     <Cmd>Notmuch tag-set +Trash -unread<CR>
nnoremap <buffer><silent>D     <Cmd>Notmuch attach-delete<CR>
vnoremap <buffer><silent>D     :Notmuch attach-delete<CR>
nnoremap <buffer><silent>o     <Cmd>Notmuch open<CR>
vnoremap <buffer><silent>o     :Notmuch open<CR>
nnoremap <buffer><2-LeftMouse> <Cmd>Notmuch open<CR>
nnoremap <buffer><silent>s     <Cmd>Notmuch attach-save<CR>
vnoremap <buffer><silent>s     :Notmuch attach-save<CR>
nnoremap <buffer><silent>S     <Cmd>Notmuch mail-save<CR>
nnoremap <buffer><silent>u     <Cmd>Notmuch tag-toggle unread<CR>
nnoremap <buffer><silent>O     <Cmd>call <SID>SwitchConceal()<CR>
nnoremap <buffer><silent>X     <Cmd>call <SID>ViewURL()<CR>

if exists('b:undo_ftplugin')
	b:undo_ftplugin ..= '| call undoftplgin#Show()'
else
	b:undo_ftplugin = 'call undoftplgin#Show()'
endif
