\ beeb_linebench_m4.asm: MODE 4S line routines, wrapped for timing in jsbeeb.
\
\ Assembled by tools/beeb_linebench.sh with beebasm in a work directory that
\ holds kieranhj/line-test's sources (rtw-linedraw.asm, nj-linedraw4.asm,
\ tricky-linedraw.asm, shallow_12_hamiltonian.asm). The screen is line-test's
\ "MODE 4S": 256 pixels wide, 1 bit a pixel, 256-byte character rows at &6000.
\
\ Elite's LOIN is the cassette version's, transcribed instruction for
\ instruction from Mark Moxon's annotated source (elite-source.asm, LOIN),
\ with its zero page given addresses of its own.
\
\ The harness calls each entry from a stub of its own at &0E00, with the end
\ points in line-test's zero page; the PRINT lines give it the entries.

\ HAMILTONIAN_12 (0 or 1) comes from the command line: beebasm -D.

scr_addr = &6000

\ line-test's zero page, as line-test.asm lays it out
ORG &70
.startx     SKIP 1
.starty     SKIP 1
.endx       SKIP 1
.endy       SKIP 1
.scrn       SKIP 2
.accum      SKIP 1
.dx         SKIP 1
.dy         SKIP 1
.count      SKIP 1
.temp       SKIP 1
y0 = starty
y1 = endy
x0 = startx
x1 = endx
scr = scrn
cnt = count
err = accum
errs = temp
.scrstrt    SKIP 1
.ls         SKIP 1

\ Elite's zero page (addresses of our own; LOIN only needs them distinct)
ORG &50
.X1         SKIP 1
.Y1         SKIP 1
.X2         SKIP 1
.Y2         SKIP 1
.P          SKIP 1
.Q          SKIP 1
.R          SKIP 1
.S          SKIP 1
.SWAP       SKIP 1
.SC         SKIP 1
.SCH        SKIP 1
.YSAV       SKIP 1

ORG &1000
GUARD &6000

.start

\ Elite's entry takes line-test's end points, as Elite's callers fill X1-Y2.
.elite_entry
    LDA startx : STA X1
    LDA starty : STA Y1
    LDA endx : STA X2
    LDA endy : STA Y2
    JMP LOIN

.nj_entry
    LDA #HI(scr_addr) : STA scrstrt
    JMP linedraw4

INCLUDE "rtw-linedraw.asm"
INCLUDE "nj-linedraw4.asm"
IF HAMILTONIAN_12
INCLUDE "shallow_12_hamiltonian.asm"
ENDIF
INCLUDE "tricky-linedraw.asm"

\ ---- Elite (cassette) LOIN, verbatim ----
.TWOS
 EQUB %10000000, %01000000, %00100000, %00010000
 EQUB %00001000, %00000100, %00000010, %00000001

.LOIN
{
 STY YSAV
 LDA #128
 STA S
 ASL A
 STA SWAP
 LDA X2
 SBC X1
 BCS LI1
 EOR #%11111111
 ADC #1
 SEC
.LI1
 STA P
 LDA Y2
 SBC Y1
 BCS LI2
 EOR #%11111111
 ADC #1
.LI2
 STA Q
 CMP P
 BCC STPX
 JMP STPY
.STPX
 LDX X1
 CPX X2
 BCC LI3
 DEC SWAP
 LDA X2
 STA X1
 STX X2
 TAX
 LDA Y2
 LDY Y1
 STA Y1
 STY Y2
.LI3
 LDA Y1
 LSR A
 LSR A
 LSR A
 ORA #&60
 STA SCH
 LDA Y1
 AND #7
 TAY
 TXA
 AND #%11111000
 STA SC
 TXA
 AND #7
 TAX
 LDA TWOS,X
 STA R
 LDA Q
 LDX #%11111110
 STX Q
.LIL1
 ASL A
 BCS LI4
 CMP P
 BCC LI5
.LI4
 SBC P
 SEC
.LI5
 ROL Q
 BCS LIL1
 LDX P
 INX
 LDA Y2
 SBC Y1
 BCS DOWN
 LDA SWAP
 BNE LI6
 DEX
.LIL2
 LDA R
 EOR (SC),Y
 STA (SC),Y
.LI6
 LSR R
 BCC LI7
 ROR R
 LDA SC
 ADC #8
 STA SC
.LI7
 LDA S
 ADC Q
 STA S
 BCC LIC2
 DEY
 BPL LIC2
 DEC SCH
 LDY #7
.LIC2
 DEX
 BNE LIL2
 LDY YSAV
 RTS
.DOWN
 LDA SWAP
 BEQ LI9
 DEX
.LIL3
 LDA R
 EOR (SC),Y
 STA (SC),Y
.LI9
 LSR R
 BCC LI10
 ROR R
 LDA SC
 ADC #8
 STA SC
.LI10
 LDA S
 ADC Q
 STA S
 BCC LIC3
 INY
 CPY #8
 BNE LIC3
 INC SCH
 LDY #0
.LIC3
 DEX
 BNE LIL3
 LDY YSAV
 RTS
.STPY
 LDY Y1
 TYA
 LDX X1
 CPY Y2
 BCS LI15
 DEC SWAP
 LDA X2
 STA X1
 STX X2
 TAX
 LDA Y2
 STA Y1
 STY Y2
 TAY
.LI15
 LSR A
 LSR A
 LSR A
 ORA #&60
 STA SCH
 TXA
 AND #%11111000
 STA SC
 TXA
 AND #7
 TAX
 LDA TWOS,X
 STA R
 LDA Y1
 AND #7
 TAY
 LDA P
 LDX #1
 STX P
.LIL4
 ASL A
 BCS LI13
 CMP Q
 BCC LI14
.LI13
 SBC Q
 SEC
.LI14
 ROL P
 BCC LIL4
 LDX Q
 INX
 LDA X2
 SBC X1
 BCC LFT
 CLC
 LDA SWAP
 BEQ LI17
 DEX
.LIL5
 LDA R
 EOR (SC),Y
 STA (SC),Y
.LI17
 DEY
 BPL LI16
 DEC SCH
 LDY #7
.LI16
 LDA S
 ADC P
 STA S
 BCC LIC5
 LSR R
 BCC LIC5
 ROR R
 LDA SC
 ADC #8
 STA SC
.LIC5
 DEX
 BNE LIL5
 LDY YSAV
 RTS
.LFT
 LDA SWAP
 BEQ LI18
 DEX
.LIL6
 LDA R
 EOR (SC),Y
 STA (SC),Y
.LI18
 DEY
 BPL LI19
 DEC SCH
 LDY #7
.LI19
 LDA S
 ADC P
 STA S
 BCC LIC6
 ASL R
 BCC LIC6
 ROL R
 LDA SC
 SBC #7
 STA SC
 CLC
.LIC6
 DEX
 BNE LIL6
 LDY YSAV
 RTS
}

.end

PRINT "start", ~start, "elite", ~elite_entry, "rtw", ~drawline
PRINT "nj", ~nj_entry, "tricky", ~draw_line, "end", ~end

IF HAMILTONIAN_12
    SAVE "LINEM4H", start, end
ELSE
    SAVE "LINEM4", start, end
ENDIF
