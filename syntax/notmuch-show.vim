" Vim syntax file
" Language: notmuch-show window
scriptversion 4

" Quit when a syntax file was already loaded
if exists('b:current_syntax')
	finish
endif

let s:cpo_save = &cpoptions
set cpoptions&vim

syntax case ignore

execute 'source ' .. expand('<sfile>:p:h:h') .. '/macros/syntax-common.vim'

syntax match	mailNewPartHead	contained	contains=@NoSpell '^[\x0C].\+ part$'
syntax match	mailNewPartHead	contained	contains=@NoSpell '^[\x0C]HTML mail$'
syntax region	mailHeader	contained	contains=mailHeaderKey,mailNewPartHead,@mailHeaderField,@NoSpell start='^[\x0C].\+ part$' skip='^\s' end='^[^:]*\n' fold
syntax region	mailNewPart	contains=mailHeader,@HTMLmailBoldlock,@mailHeaderField,@NoSpell start='^[\x0C].\+ part$' end='^[\x0C]'me=e-1 fold
syntax region	mailNewPart	contains=mailHeader,@HTMLmailBoldlock,@mailHeaderField,@NoSpell start='^[\x0C].\+ mail$' end='^[\x0C]'me=e-1
syntax region	HTMLmail	contains=mailNewPartHead,@HTMLmailBoldlock,@NoSpell start='^[\x0C]HTML part$' end='^[\x0C]'me=e-1 end='\%$' fold
syntax region	HTMLmail	contains=mailNewPartHead,@HTMLmailBoldlock,@NoSpell start='^[\x0C]HTML mail$' end='^[\x0C]'me=e-1 end='\%$'

 " marddown
" syntax cluster	HTMLmailInline	contains=HTMLmailLinkText,HTMLmailItalic,HTMLmailBold,HTMLmailBoldItalic
syntax cluster	HTMLmailInline	contains=HTMLmailLinkText,HTMLmailItalic,HTMLmailBold
syntax cluster	HTMLmailBoldlock	contains=HTMLmailH1,HTMLmailH2,HTMLmailH3,HTMLmailH4,HTMLmailH5,HTMLmailH6,@HTMLmailInline,HTMLmailLink,HTMLmailId

syntax region	HTMLmailItalic	contained	matchgroup=HTMLmailItalicTag start="_" end="_" skip="\\_"	contains=HTMLmailLinkBoldItalic,@Spell,HTMLmailLink,HTMLmailLinkText concealends keepend
syntax region	HTMLmailBold	contained	matchgroup=HTMLmailBoldTag start="\*\*" end="\*\*" skip="\\\*"	contains=HTMLmailLinkBoldItalic,@Spell,HTMLmailLink,HTMLmailLinkText concealends keepend
" syntax region	HTMLmailBoldItalic	contained	matchgroup=HTMLmailBoldItalicTag start="_\*\*" end="\*\*_\w\@!" skip="\\_\|\\\*"	contains=@Spell,HTMLmailLink,HTMLmailLinkText concealends keepend
" syntax region	HTMLmailBoldItalic	contained	matchgroup=HTMLmailBoldItalicTag start='\*\*_' end='_\*\*\s' skip="\\_\|\\\*"	contains=@Spell,HTMLmailLink,HTMLmailLinkText concealends keepend
syntax region	HTMLmailLinkBoldItalic	contained	matchgroup=HTMLmailBoldItalicTag start="_" end="_" skip="\\_"	contains=@Spell,HTMLmailLink,HTMLmailLinkText concealends keepend
syntax region	HTMLmailLinkBoldItalic	contained	matchgroup=HTMLmailBoldItalicTag start="\*\*" end="\*\*" skip="\\\*"	contains=@Spell,HTMLmailLink,HTMLmailLinkText concealends keepend

if get(g:, 'notmuch_conceal_url', 0)
	syntax region	HTMLmailLink	contained	matchgroup=HTMLmailLinkTag start="(" end=")"	contains=mailURL keepend oneline conceal
else
	syntax region	HTMLmailLink	contained	matchgroup=HTMLmailLinkTag start="(" end=")"	contains=mailURL keepend oneline
endif
syntax region	HTMLmailId	contained	matchgroup=HTMLmailIdTag start="\[" end="\]" keepend oneline
syntax region	HTMLmailLinkText	contained	matchgroup=HTMLmailLinkTextTag start="!\=\[\%(\%(\_[^][]\|\[\_[^][]*\]\)*]\%( \=[[(]\)\)\@=" end="\]\%( \=[[(]\)\@=" nextgroup=HTMLmailLink,HTMLmailId skipwhite	contains=@HTMLmailInline,HTMLmailLinkItalic,HTMLmailLinkBold keepend
syntax region	HTMLmailLinkItalic	contained	matchgroup=HTMLmailLinkItalicTag start="_" end="_"  skip="\\_"	contains=@Spell concealends keepend
syntax region	HTMLmailLinkBold	contained	matchgroup=HTMLmailLinkBoldTag start="\*\*" end="\*\*" skip="\\\*"	contains=@Spell concealends keepend

syntax match	HTMLmailH1	contained	contains=@NoSpell,@HTMLmailInline,mailURL '^#\{2} .\+$'
syntax match	HTMLmailH2	contained	contains=@NoSpell,@HTMLmailInline,mailURL '^#\{3} .\+$'
syntax match	HTMLmailH3	contained	contains=@NoSpell,@HTMLmailInline,mailURL '^#\{4} .\+$'
syntax match	HTMLmailH4	contained	contains=@NoSpell,@HTMLmailInline,mailURL '^#\{5} .\+$'
syntax match	HTMLmailH5	contained	contains=@NoSpell,@HTMLmailInline,mailURL '^#\{6} .\+$'
syntax match	HTMLmailH6	contained	contains=@NoSpell,@HTMLmailInline,mailURL '^#\{7} .\+$'

highlight default link HTMLmailH1	Title
highlight default link HTMLmailH2	Title
highlight default link HTMLmailH3	Title
highlight default link HTMLmailH4	Title
highlight default link HTMLmailH5	Title
highlight default link HTMLmailH6	Title
highlight default link HTMLmailLinkText	Underlined
highlight default link HTMLmailId	Type
highlight default link HTMLmailBold	htmlBold
highlight default link HTMLmailBoldTag	htmlBold
" highlight default link HTMLmailBoldItalic	htmlBoldItalic
highlight default link HTMLmailLinkBoldItalic	htmlBoldItalic
highlight default link HTMLmailBoldItalicTag htmlBoldItalic
highlight default link HTMLmailItalic	htmlItalic
highlight default link HTMLmailItalicTag	htmlItalic
highlight default link HTMLmailLinkItalic htmlLinkItalic
highlight default link HTMLmailLinkBold htmlLinkBold
highlight default link HTMLmailLinkItalicTag htmlLinkItalic
highlight default link HTMLmailLinkBoldTag htmlLinkBold

let highlight_string = notmuch_py#Get_highlight('Normal')
if highlight_string =~# '\<term='
	let highlight_it = substitute(highlight_string, '\<term=', 'term=italic,', 'g')
	let highlight_b = substitute(highlight_string, '\<term=', 'term=bold,', 'g')
	let highlight_bi = substitute(highlight_string, '\<term=', 'term=bold,italic,italic,', 'g')
else
	let highlight_it = highlight_string ..' term=italic'
	let highlight_b = highlight_string ..' term=bold'
	let highlight_bi = highlight_string ..' term=bold,italic'
endif
if highlight_string =~# '\<cterm='
	let highlight_it = substitute(highlight_it, '\<cterm=', 'cterm=italic,', 'g')
	let highlight_b = substitute(highlight_b, '\<cterm=', 'cterm=bold,', 'g')
	let highlight_bi = substitute(highlight_b, '\<cterm=', 'cterm=bold,italic,', 'g')
else
	let highlight_it = highlight_it ..' cterm=italic'
	let highlight_b = highlight_b ..' cterm=bold'
	let highlight_bi = highlight_b ..' cterm=bold,italic'
endif
if highlight_string =~# '\<gui='
	let highlight_it = substitute(highlight_it, '\<gui=', 'gui=italic,', 'g')
	let highlight_b = substitute(highlight_b, '\<gui=', 'gui=bold,', 'g')
	let highlight_bi = substitute(highlight_b, '\<gui=', 'gui=bold,italic,', 'g')
else
	let highlight_it = highlight_it ..' gui=italic'
	let highlight_b = highlight_b ..' gui=bold'
	let highlight_bi = highlight_b ..' gui=bold,italic'
endif
execute 'highlight htmlBold ' .. highlight_b
execute 'highlight htmlItalic ' .. highlight_it
execute 'highlight htmlBoldItalic ' .. highlight_bi
let highlight_string = notmuch_py#Get_highlight('Underlined')
if highlight_string =~# '\<term='
	let highlight_it = substitute(highlight_string, '\<term=', 'term=italic,', 'g')
	let highlight_b = substitute(highlight_string, '\<term=', 'term=bold,', 'g')
else
	let highlight_it = highlight_string ..' term=italic'
	let highlight_b = highlight_string ..' term=bold'
endif
if highlight_string =~# '\<cterm='
	let highlight_it = substitute(highlight_it, '\<cterm=', 'cterm=italic,', 'g')
	let highlight_b = substitute(highlight_b, '\<cterm=', 'cterm=bold,', 'g')
else
	let highlight_it = highlight_it ..' cterm=italic'
	let highlight_b = highlight_b ..' cterm=bold'
endif
if highlight_string =~# '\<gui='
	let highlight_it = substitute(highlight_it, '\<gui=', 'gui=italic,', 'g')
	let highlight_b = substitute(highlight_b, '\<gui=', 'gui=bold,', 'g')
else
	let highlight_it = highlight_it ..' gui=italic'
	let highlight_b = highlight_b ..' gui=bold'
endif
execute 'highlight htmlLinkItalic ' .. highlight_it
execute 'highlight htmlLinkBold ' .. highlight_b
unlet highlight_string
unlet highlight_it
unlet highlight_b
unlet highlight_bi

let b:current_syntax = 'notmuch-show'

let &cpoptions = s:cpo_save
unlet s:cpo_save
