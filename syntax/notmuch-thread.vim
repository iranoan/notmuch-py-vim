scriptencoding utf-8

syntax region tagMailU    start='^📩'       end='$' contains=Border
syntax region tagMailF    start='^⭐'       end='$' contains=Border
syntax region tagMailT    start='^🗑'       end='$' contains=Border
syntax region tagMailD    start='^📝'       end='$' contains=Border
syntax region tagMailFT   start='^⭐🗑'     end='$' contains=Border
syntax region tagMailDT   start='^📝🗑'     end='$' contains=Border
syntax region tagMailDF   start='^📝⭐'     end='$' contains=Border
syntax region tagMailUF   start='^📩⭐'     end='$' contains=Border
syntax region tagMailUT   start='^📩🗑'     end='$' contains=Border
syntax region tagMailUD   start='^📩📝'     end='$' contains=Border
syntax region tagMailUDF  start='^📩📝⭐'   end='$' contains=Border
syntax region tagMailUDT  start='^📩📝🗑'   end='$' contains=Border
syntax region tagMailDFT  start='^📝⭐🗑'   end='$' contains=Border
syntax region tagMailUFT  start='^📩⭐🗑'   end='$' contains=Border
syntax region tagMailUDFT start='^📩📝⭐🗑' end='$' contains=Border

if get(g:, 'notmuch_visible_line', 0) == 3
	syntax match Border "\t" conceal cchar=│
endif

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
