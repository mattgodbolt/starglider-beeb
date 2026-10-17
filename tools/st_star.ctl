# Control file for tools/st_disasm.py on Starglider's AUTO/STAR.PRG (Atari ST).
# Addresses are offsets into the text segment (the program loads at base 0
# here; EmuTOS loads it at &109BE, so add that to compare with Hatari PCs).
# See docs/research/st.md.
#
#   c ADDR [NAME]   code root      l ADDR NAME   label
#   t ADDR N l [STRIDE] / t ADDR N w [BASE]      jump table
#   d ADDR END      force data     ; ADDR TEXT   comment

l &00000 start
; &01E5A Entry (the bra at &00000 lands here). a6 = &5BF00 (fixed RAM, not relocated) holds the game's variables
l &01E5A main
; &01F10 The per-frame loop: render, keys, flight, objects, animation, collisions, messages, frame end
l &01F10 frame_loop

# Interrupts
c &000A2 vbl_handler
; &000A2 VBL: counts the absolute word &1E4 and counts down &29C. Nothing else
c &00C32 acia_handler
; &00C32 Keyboard into the key-state array &17C2; mouse x/y into &1842/&1844 (&1848 with the right button)
c &01AF8 sample_timer_a
; &01AF8 Timer A: one sample byte a tick through a self-modified address (&1B00), 3x256 YM volume table at &1B4A
l &01B4A ym_volume_table
l &01A50 sample_start
l &00110 sfx_start
l &01854 sfx_table

# Start-up
l &0A534 linea_hide_mouse
l &08CA0 init_resolution
; &08CA0 Sets the view window, centres and function pointers for colour (low res) or mono (high res)
l &0493A detect_resolution
l &08E56 set_startup_palette
l &08E82 startup_palette
l &032EC load_pictures
l &0AACA tra_unpack
l &0ABF6 tra_chunky_planar_table
l &0A6AE init_objects
; &0A6AE Clears the 140 64-byte object records at &129A(a6) and fills them from the level's list (&17C88)
l &17C88 level_lists

# Frame
l &04FE8 world_render
l &099CA view_clear_call
l &08EC2 frame_end
; &08EC2 Wait for the raster to pass line 192 (&FF8207), colour 0 from &242(a6), then swap screens
l &0A548 wait_raster_192
l &0A54A wait_vbl
l &0A56E swap_screens
l &0270E read_keys
l &077B4 player_flight
l &07A54 object_handlers
l &08252 object_handler_table
l &043EE animate_shapes
l &08416 collisions
l &0260C level_message
l &0866C player_laser
l &07E18 enemy_laser
l &08390 angle_to_player
l &04692 random32
l &046B2 random8

# 3D
l &04114 build_object_matrix
l &03FFE transform_vertex
l &04B1C draw_shape
; &04B1C Shape renderer: back-face test per face (skipped while &2BD(a6) is set), then transform marked vertices and draw marked edges
l &04DAC draw_shape_exploding
l &04D66 project_and_draw_edge
l &0A374 clip_near
l &0A170 clip_2d
l &08FE6 draw_line_call
l &0AC76 type_to_shape
l &0AF4E shape_table
l &0B11E shape_data
l &13568 arctan_table_a
l &1396A arctan_table_b
l &13D6C sine_table
l &16D88 font_colour
l &170E8 font_mono

# Function pointers set by init_resolution: colour, then mono
c &09128 line_colour
c &0976E dot_colour
c &012EC print_colour_38
c &01264 print_colour_3c
c &099D0 view_clear_colour
c &09842 blit_colour
c &08FEC line_mono
c &097F8 dot_mono
c &01184 print_mono_38
c &01134 print_mono_3c
c &0A0A8 view_clear_mono
c &09938 blit_mono

# Panel
l &05872 waveforms
l &05E0C scanner_colour
l &09D38 view_flash_white

# Pointer tables
t &01854 24 l 8
t &08252 62 l
t &09174 16 l
t &091BA 16 l
