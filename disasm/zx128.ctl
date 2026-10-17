; Starglider 128 (Realtime Games, v.11/86), the 64K view with bank 0 at &C000.
; From tools/zx.py runs: sna2skool.py -H -p 0 -c disasm/zx128.ctl build/zx128.z80
; Titles are from docs/research/zx.md; the rest is sna2ctl's guess from an
; execution map. Bank 4 (front end) and bank 6 (tune) need -p 4 and -p 6.

@ $4000 start
@ $4000 org
b $4000 Sine tables: &4100 sin(n*2pi/256)*127, &4000 the same half a step on (9-bit angles); cosine at +&40
t $400A
b $4015
t $4016
b $4020
t $4023
b $4034
t $404C
b $405D
t $4060
b $406A
t $406B
b $4076
t $410B
b $4122
t $4123
b $4135
t $414C
b $415E
t $415F
b $4176
t $4209
b $420C
t $4212
b $4217
t $4223
b $4229
t $422A
b $422D
t $4246
b $4252
t $4254
b $425A
t $428C
b $42A4
t $42A7
b $42B3
t $442B
b $442F
t $4430
b $4452
t $4453
b $4471
t $4477
b $4491
t $4509
b $450C
t $4511
b $4514
t $456D
b $4570
t $4575
b $4578
t $4589
b $458C
t $4591
b $4594
t $45ED
b $45F0
t $45F5
b $45F8
t $465B
b $465F
t $4660
b $4680
t $4681
b $46A1
t $46A2
b $46A6
t $48CB
b $48CE
t $48D3
b $48D6
t $4D26
b $4D29
t $568F
b $5699
t $7FF2
b $7FF5
t $8169
b $816C
c $8181 IM 2 jump to the interrupt handler at &A86D
b $8193
c $8500 Game entry: IM 2, keep the loading picture, build the screen line table, start
b $8546
c $8549 Page bank A at &C000 (always with ROM 1 and the bank 7 screen: OR &18); remembers it in &5716
c $8556 Silo computer: the enemy file
c $8589 Silo computer: show enemy A (records at &8688: type, distance, height, name, text)
c $85F8 Silo computer: draw the enemy's shape
t $863F
b $8642
t $865A
b $8677
t $8678
b $8687
t $86B1
b $86C6
t $86C7
b $86E3
t $86E4
b $8703
t $8709
b $871E
t $871F
b $873E
t $873F
b $8751
t $8757
b $875C
t $875D
b $877B
t $877C
b $879B
t $87A1
b $87AC
t $87AD
b $87CB
t $87CC
b $87E7
t $87ED
b $87FC
t $87FD
b $881B
t $881C
b $8837
t $883D
b $8856
t $8857
b $8871
t $8872
b $8880
t $8886
b $8896
t $8897
b $88B1
t $88B2
b $88CC
t $88D2
b $88E6
t $88E7
b $8902
t $8903
b $8919
t $891F
b $892A
t $892B
b $8948
t $8949
b $8966
t $896C
b $8972
t $8973
b $898F
t $8990
b $899B
t $89A1
b $89AC
t $89AD
b $89C7
t $89C8
b $89E7
t $89ED
b $89F7
t $89F8
b $8A17
t $8A18
b $8A33
t $8A39
b $8A49
t $8A4A
b $8A66
t $8A67
b $8A83
t $8A89
b $8A94
t $8A95
b $8AB2
t $8AB3
b $8AC1
t $8AC7
b $8AD6
t $8AD7
b $8AF4
t $8AF5
b $8B05
t $8B0B
b $8B1E
t $8B1F
b $8B3E
t $8B3F
b $8B59
t $8B5F
b $8B6E
t $8B6F
b $8B8C
t $8B8D
b $8BA4
t $8BAA
b $8BB7
t $8BB8
b $8BD4
t $8BD5
b $8BEE
c $8BEF Speak phrase A (table at &8C92: start, length, delay, bank); interrupts off
b $8C8C
c $8CAA Speech: the two bleeps before a phrase
c $8CCF Delay BC x 26 T-states
c $8CD5
c $8CE5
b $8CFB
c $8CFC Plot a point (1, 2 or 4 pixels) in the view buffer (bank 7 &E800)
c $8D6F Draw a line in the view buffer (pages bank 7)
c $8D85 Draw a line (Bresenham) into the 256x128 view buffer, writing the ink at &5632 into each attribute cell it crosses
c $8F20
c $8F29
c $8F43
c $8F74
s $8FAB
c $8FAC Read a keyboard half-row
c $8FC2
c $8FD1
c $8FE6 Read a key
c $900C
s $904C
t $904D
b $906A
t $906B
s $9070
t $9071
s $9074
t $9075
b $9084
t $9085
b $9088
t $9089
b $9092
t $9093
s $9098
t $9099
b $909C
t $909D
b $90BA
t $90BB
b $90C0
t $90C1
c $90C4
b $9191
c $91C1
c $91C8
c $91F7 Copy the view (30 bytes x 120 lines and 30 x 15 attributes) from the buffer to the screen
c $9299 Clear the view buffer (PUSH) and fill its attributes with &5710
c $92CF Copy the view to the screen (missile view)
c $9372
c $93A8
c $9420
c $945F
c $9478
c $94B6 Clear the vertex buffer
c $94C4 End of pass: set &5634 and wait for the frame interrupt, which copies and clears the view
c $94CB
c $94EC
c $950C
c $9539 Copy the loading picture (bank 7) to bank 6 &E500
b $9560 Swap bank 5 &4000-&5AFF with bank 6 &E500 (the title picture)
c $95B9
c $95CE
c $95F5 Print the string after the CALL (last character has bit 7 set)
c $961D
c $964B
c $9686
c $96B6
c $96BF
c $96C6
c $96DE
b $9702
t $9706
b $970E
t $9713
b $9728
t $972D
b $9743
t $9748
b $975E
t $9763
b $976C
c $976D
b $9788
t $978C
b $9794
c $9795 Put an object on the scanner
c $97D0
b $97F3
c $9895
c $98BB
c $98C9
c $9909
c $995C
c $99B3
c $99BD
b $99EA
t $9A33
b $9A38
t $9A7C
b $9A7F
t $9A93
b $9A96
t $9ADD
b $9AE0
c $9B14
c $9B28 Panel bars: energy, shields, laser (speaks phrases 2 and 3 when shields or energy run low)
c $9C75
c $9C8C
s $9CBC
c $9CBE
c $9CE5
c $9D02
c $9D4C
t $9D54
c $9D58
c $9D6B
c $9D81
b $9DBC
c $9DC2
c $9DD1
c $9DE7
b $9E09
c $9E27
c $9E35
c $9E3C
b $9E47
c $9E4A
b $9E52
t $9E55
b $9E5B
c $9E5D
c $9E62
b $9E6A
c $9E72
b $9E79
c $9E80
c $9E87
b $9E8E
c $9E95
c $9E9C
c $9EAA
c $9EB8
c $9EC6
c $9ECF
c $9EDC
c $9EF3
c $9F17
c $9F1D
t $9F3F
b $9F45
c $9F46
c $9F8E
c $9FAA
b $9FB3
c $9FBD
c $9FD4
c $9FE6
c $A0A3
c $A0B8
c $A164
c $A185
c $A1A2
b $A1DB
c $A25A
c $A26C
b $A2F6
c $A2F9
s $A34D
c $A34E
c $A362
c $A36A
c $A373
c $A378
b $A38C
c $A3CA
b $A3D8
c $A3F9
c $A426
c $A453
c $A480
c $A491
b $A4D7
t $A4E4
b $A4E7
c $A508 Draw the objects in view, far to near (walk the depth tree)
c $A538
c $A53B
c $A562 Clear the object table
b $A572
c $A57E Font address of character A (bank 7 &DB00)
c $A590 Write the AY's 14 registers from the shadow at &5717
c $A5A9
c $A62C
b $A687
t $A697
b $A69A
t $A6AD
b $A6BA
t $A6C1
b $A6C4
t $A6CB
b $A6CE
t $A6E1
b $A6F1
t $A6F8
b $A6FB
c $A6FE
c $A714
c $A77C
c $A787
c $A7E1
c $A836
b $A852
t $A857
b $A85B
t $A85F
b $A864
c $A86D Interrupt handler (IM 2): page bank 7 and do the frame's work
c $A8A0 Frame work: after a pass, wait for the raster, copy and clear the view; sound; missile view
b $AAFF
t $AB09
b $AB0C
t $AB13
b $AB16
t $AB1A
b $AB1D
c $AB22
s $AB49
c $AB4A
c $AB7C
c $ABA2
c $ABD1 Open the missile view (speaks phrase 0)
c $AC0F
c $AC3C
c $AC71
c $ACF2
c $AD2C Front end (bank 4 &C24D), then start a game
c $AD46
c $AD5E
c $ADCF
c $ADE7
c $AE6A
c $AE7C
c $AE81
c $AE87
c $AEAE Sound off
c $AEBE
c $AF3A
c $AF4D
c $AFB8
c $B09E
b $B27E
t $B2AF
b $B2B2
t $B2BA
b $B2C8
t $B2D1
b $B2EB
t $B2EF
b $B2F2
t $B300
b $B304
t $B351
b $B354
t $B38E
b $B391
t $B410
b $B414
t $B45C
b $B469
t $B46A
b $B47A
t $B47B
b $B484
t $B485
b $B491
t $B492
b $B4A0
t $B4A1
b $B4AE
t $B4C8
b $B4DF
t $B4ED
b $B4F0
t $B4F6
b $B4F9
t $B503
b $B506
t $B50E
b $B513
t $B524
b $B52A
t $B545
b $B549
t $B677
b $B684
t $B68B
b $B694
t $B6A7
b $B6C3
t $B6C5
b $B6D9
t $B6DA
b $B6E6
t $B6E8
b $B706
t $B707
b $B720
t $B721
b $B728
t $B72B
b $B74A
t $B74C
b $B76C
t $B76D
b $B78C
t $B78D
b $B7AA
t $B7AB
b $B7BD
t $B7C0
b $B7D1
t $B7D3
b $B7F1
t $B7F2
b $B812
t $B813
b $B82D
t $B82F
b $B84C
t $B84E
b $B86C
t $B86E
b $B88E
t $B890
b $B8AF
t $B8B1
b $B8CF
t $B8D0
b $B8E8
t $B8EA
b $B902
t $B903
b $B921
t $B923
b $B942
t $B943
b $B963
t $B964
b $B968
t $B96B
b $B98B
t $B98C
b $B99D
t $B99F
b $B9BE
t $B9BF
b $B9DB
t $B9DC
b $B9E7
t $B9E9
b $BA00
t $BA01
b $BA20
t $BA22
b $BA36
t $BA39
b $BA59
t $BA5A
b $BA70
t $BA8D
b $BAA3
t $BAA4
b $BAA9
t $BABC
b $BAC1
t $BACB
b $BACF
t $BB51
b $BB55
t $BB5D
b $BB64
t $BB8B
b $BB97
t $BB98
b $BB9B
t $BB9E
b $BBA1
t $BBA5
b $BBAB
t $BBB3
b $BBB6
t $BBBC
b $BBC0
c $BBE8 Silence the AY (shadow and chip)
c $BC11
c $BC17
c $BC1D
b $BC23
c $BC29
c $BC34
c $BC43
c $BC58
c $BC6B
c $BC8C
c $BD6C
c $BD73
b $BD79
c $BD7A
c $BD8F Signed 8x8 multiply by quarter squares (&4500)
c $BDC2 Signed 8x8 multiply, rounded high byte
c $BE03 Signed 16x8 multiply
c $BE70 Perspective divide for x: x*K/z by logarithms (&4200) and antilogarithms (&4400)
c $BF1E Perspective divide for y
b $BFA4
c $BFB1
b $C073
t $C083
b $C089
c $C08B Project the shape's vertices: X = 128 + x*K/z, Y = 64 + y*K/z (K about 250); behind the viewer: &8000
c $C0E5 Project the object's centre
c $C111 Face test: does the face through three projected vertices face the viewer?
c $C233
c $C240 Sine and cosine of the object's yaw plus the viewer's heading
b $C25B
c $C25E
c $C26B Sine and cosine of the viewer's pitch
c $C282 Sine and cosine of the viewer's heading
c $C299 Sine and cosine of the viewer's roll
c $C2B0
s $C2E4
c $C2E6
s $C31A
c $C31C
s $C350
c $C352
s $C386
c $C388
s $C3BB
c $C3BF Rotate (x, z) by the viewer's heading
s $C3F2
c $C3F6
s $C429
c $C42D
s $C460
c $C464
b $C486
c $C623 Basis routine (missiles, pod, scanner)
c $C798 Basis routine (box): rotate the axes, scale by the sizes
c $C82B Basis routine (towers)
c $C84A Basis routine (walker): box, then the legs from the animation table at &C8CF
c $C8A9
b $C8CD
c $C99B
b $C9BE
c $CB56
b $CB62
c $CBC2
b $CC85
t $CD74
b $CD77
c $CE8B Draw the marked face-culled edges
c $CE9F Draw the always-drawn edges
c $CEB6 Draw an edge if marked
c $CF7B
c $CF7E
c $CF81
c $CF83
c $D00E
c $D01E
c $D025
c $D06F
c $D096
c $D0BF
c $D0DA Run a shape's vertex program (ops: 00 load, 01 store, 10 midpoint, 11 add)
c $D173 Move the objects; cull beyond 9000 units; into view space; scanner
s $D2EC
c $D2EE Shape dispatch: call the shape's basis routine, return to &D304
c $D304 Draw a shape: vertex program, projection, edges, faces
s $D3AA
c $D3AC Draw an object (HL: its depth-tree node)
c $D3F9 Draw the horizon (dotted)
b $D4D3
t $D686
b $D689
t $D6D0
b $D6D3
t $D701
b $D704
t $D731
b $D735
c $D932
b $D95F
c $D9B1 Ground marker dots (10, table at &DB9B)
s $DB36
c $DB3A
c $DB6A
c $DB7C
b $DB9B
c $DBC3
c $DBEA
c $DC0E
c $DC36
c $DC3F
b $DC65
c $DCA8
b $DCB4
c $DCBE
b $DCC4
c $DCD0
c $DCE1
b $DCED
c $DCFE
c $DD28
b $DD9C
t $DDBE
b $DDC1
c $DDE0
c $DE0A
c $DE37
c $DE69
c $DEBA
c $DF0E
c $DF27
c $DF73
c $DFFF
c $E04E
b $E09D
c $E113
c $E18A
b $E21F
t $E283
b $E286
t $E3A0
b $E3A3
t $E3AD
b $E3B0
t $E41A
b $E41D
t $E432
b $E435
t $E440
b $E443
t $E447
b $E44A
t $E451
b $E455
t $E4A4
b $E4A7
t $E4B5
b $E4B8
c $E4C2
c $E4CD
c $E4D4
c $E4DA
c $E4F3
c $E4F8
c $E697
c $E69B
c $E6A3
c $E706
c $E77D
c $E78B
c $E794
b $E7D0
c $E8DE
b $E8EE
t $E906
b $E909
t $E942
b $E945
c $EA2B
c $EBAC
c $EBF3
b $EC1C
c $EC5A
c $EE24
c $EE41
b $EE5D
b $4200 Logarithm table for the perspective divide (low bytes &4200, high bytes &4300)
b $4400 Antilogarithm (exponent) table for the perspective divide
b $4500 Quarter-square table n*n/4 for the multiplies (low bytes &4500, high bytes &4600)
b $4700 Screen line addresses in bank 7, 128 lines (built at &8530)
b $4A00 Depth tree of the objects in view (walked by &A508)
b $4B00 Vertex buffer: 6-byte x, y, z slots, overwritten by 4-byte screen x, y after projection; slots 34-41 are the box corners
b $4C00 Object table: 128 objects of 20 bytes (+0 flags and ink, +1 x, +5 z, +7 animation, +8 yaw, +9 type, +12/+14 camera x/y, replaced by screen x/y by &C0E5)
b $5600 Variables (&5634 pass done, &5637 missile view, &56AA/&56AE viewer x/z, &56B0/&56B2/&56B4 heading/pitch/roll, &56B8 energy, &56BB shields, &56FC object count, &5716 paging, &5717 AY shadow)
b $5800 Shapes: types 0-35, each a basis routine, sizes, a vertex program, edge lists and faces (docs/research/zx.md)
w $6DCE Shape pointer table, by object type
b $8000 IM 2 vector table (257 bytes of &81)
b $8200 Speech: AY volumes for channels A, B and C (&8200, &8300, &8400) for each sample value
c $958B Attract mode: show the title picture and play the tune (bank 6) until a key
c $AD67 Main loop: one pass draws one frame of the view
c $C48A Basis routine (mines)
c $C6AA Box corners (vertex slots 34-41) from the basis vectors and the object's position
c $CEC0 Draw an edge: ink, clip by midpoint subdivision, draw
c $D7B8 Draw a type &20 object (a link between two objects)
