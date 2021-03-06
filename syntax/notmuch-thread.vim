scriptencoding utf-8

syntax region	tagMailU		start='^๐ฉ' end='$'
syntax region	tagMailF		start='^โญ' end='$'
syntax region	tagMailT		start='^๐' end='$'
syntax region	tagMailD		start='^๐' end='$'
syntax region	tagMailFT		start='^โญ๐' end='$'
syntax region	tagMailDT		start='^๐๐' end='$'
syntax region	tagMailDF		start='^๐โญ' end='$'
syntax region	tagMailUF		start='^๐ฉโญ' end='$'
syntax region	tagMailUT		start='^๐ฉ๐' end='$'
syntax region	tagMailUD		start='^๐ฉ๐' end='$'
syntax region	tagMailUDF	start='^๐ฉ๐โญ' end='$'
syntax region	tagMailUDT	start='^๐ฉ๐๐' end='$'
syntax region	tagMailDFT	start='^๐โญ๐' end='$'
syntax region	tagMailUFT	start='^๐ฉโญ๐' end='$'
syntax region	tagMailUDFT	start='^๐ฉ๐โญ๐' end='$'
syntax match	Entity	"[\u200b]" conceal cchar=  " Subject ใ็ฉบใฎๆใฎไปฃไพกๆๅญ (ใฟใๆๅญใฎไฝ็ฝฎใใใใใฎใๆฌ ็น)

" Subject ใ็ฉบใฎๆใฎไปฃไพกๆๅญใฏ Normal ใฎ่ๆฏ่ฒใจๅใใซใใ (ใซใผใฝใซ่กใฎ่ฒ Cursor ใใๅชๅใใใใฎใๆฌ ็น)
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
