onerror {resume}
quietly WaveActivateNextPane {} 0
add wave -noupdate -radix hexadecimal /top_tb/dut/sataphy_host_source_payload_d
add wave -noupdate /top_tb/dut/sataphy_host_source_stb
add wave -noupdate -radix hexadecimal /top_tb/dut/sataphy_device_source_payload_d
add wave -noupdate -radix hexadecimal /top_tb/dut/sataphy_device_source_stb
add wave -noupdate -radix hexadecimal /top_tb/refclk_p
add wave -noupdate -radix hexadecimal /top_tb/refclk_n
add wave -noupdate -radix hexadecimal /top_tb/clk200_p
add wave -noupdate -radix hexadecimal /top_tb/clk200_n
add wave -noupdate -radix hexadecimal /top_tb/sata_txp
add wave -noupdate -radix hexadecimal /top_tb/sata_txn
add wave -noupdate -radix hexadecimal /top_tb/sata_rxp
add wave -noupdate -radix hexadecimal /top_tb/sata_rxn
TreeUpdate [SetDefaultTree]
WaveRestoreCursors {{Cursor 1} {16623348 ps} 0} {{Cursor 2} {21767465 ps} 0}
quietly wave cursor active 1
configure wave -namecolwidth 446
configure wave -valuecolwidth 100
configure wave -justifyvalue left
configure wave -signalnamewidth 0
configure wave -snapdistance 10
configure wave -datasetprefix 0
configure wave -rowmargin 4
configure wave -childrowmargin 2
configure wave -gridoffset 0
configure wave -gridperiod 1
configure wave -griddelta 40
configure wave -timeline 0
configure wave -timelineunits ps
update
WaveRestoreZoom {0 ps} {17730427 ps}
