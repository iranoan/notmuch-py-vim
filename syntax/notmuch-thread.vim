scriptencoding utf-8

syntax region	tagMailU		start='^📩' end='$'
syntax region	tagMailF		start='^⭐' end='$'
syntax region	tagMailT		start='^🗑' end='$'
syntax region	tagMailD		start='^📝' end='$'
syntax region	tagMailFT		start='^⭐🗑' end='$'
syntax region	tagMailDT		start='^📝🗑' end='$'
syntax region	tagMailDF		start='^📝⭐' end='$'
syntax region	tagMailUF		start='^📩⭐' end='$'
syntax region	tagMailUT		start='^📩🗑' end='$'
syntax region	tagMailUD		start='^📩📝' end='$'
syntax region	tagMailUDF	start='^📩📝⭐' end='$'
syntax region	tagMailUDT	start='^📩📝🗑' end='$'
syntax region	tagMailDFT	start='^📝⭐🗑' end='$'
syntax region	tagMailUFT	start='^📩⭐🗑' end='$'
syntax region	tagMailUDFT	start='^📩📝⭐🗑' end='$'
syntax match	Entity	"[\u200b]" conceal cchar=  " Subject が空の時の代価文字 (タブ文字の位置がずれるのが欠点)

" Subject が空の時の代価文字は Normal の背景色と同じにする (カーソル行の色 Cursor より優先されるのが欠点)
" function s:ZeroWidthSpace() abort
" 	let l:bg = matchstr(execute('highlight Normal'), '\<ctermbg=\zs[^ ]\+')
" 	if l:bg !=# ''
" 		let l:bg = 'ctermfg=' .. l:bg .. ' ctermbg=' .. l:bg
" 	endif
" 	let l:gbg = matchstr(execute('highlight Normal'), '\<guibg=\zs[^ ]\+')
" 	if l:gbg !=# ''
" 		let l:bg ..= ' guifg=' .. l:gbg .. ' guibg=' .. l:gbg
" 	endif
" 	execute 'highlight ZeroWidthSpace ' .. l:bg
" endfunction
" call s:ZeroWidthSpace()
" call matchadd('ZeroWidthSpace', "[\u200B]")

highlight tagMailU    cterm=bold           gui=bold
highlight tagMailF    cterm=underline      gui=underline
highlight tagMailT                                            ctermfg=10 guifg=darkgray
highlight tagMailD    cterm=bold           gui=bold
highlight tagMailFT   cterm=underline      gui=underline      ctermfg=10 guifg=darkgray
highlight tagMailDT   cterm=bold           gui=bold           ctermfg=10 guifg=darkgray
highlight tagMailDF   cterm=bold,underline gui=bold,underline
highlight tagMailUF   cterm=bold,underline gui=bold,underline
highlight tagMailUT   cterm=bold           gui=bold           ctermfg=10 guifg=darkgray
highlight tagMailUD   cterm=bold           gui=bold
highlight tagMailUDF  cterm=bold,underline gui=bold,underline
highlight tagMailUDT  cterm=bold           gui=bold           ctermfg=10 guifg=darkgray
highlight tagMailDFT  cterm=bold           gui=bold           ctermfg=10 guifg=darkgray
highlight tagMailUFT  cterm=bold,underline gui=bold,underline ctermfg=10 guifg=darkgray
highlight tagMailUDFT cterm=bold,underline gui=bold,underline ctermfg=10 guifg=darkgray

highlight notmuchMark term=bold cterm=bold gui=bold ctermfg=red guifg=red
