#!/bin/bash
set -ex
rm -rf /home/w011247/mpbuild
cp -a /mnt/c/Git/micropython-jpc /home/w011247/mpbuild
ls -la /home/w011247/mpbuild/ports/esp32/sai_addressing.c
ls -la /home/w011247/mpbuild/ports/esp32/boards/JACKPACK_ESP32/mpconfigboard.h
source /home/w011247/esp/esp-idf/export.sh
cd /home/w011247/mpbuild/mpy-cross
make -j4
cd /home/w011247/mpbuild/ports/esp32
make BOARD=JACKPACK_ESP32 -j4
cp /home/w011247/mpbuild/ports/esp32/build-JACKPACK_ESP32/micropython.bin /mnt/c/Git/micropython-jpc/
cp /home/w011247/mpbuild/ports/esp32/build-JACKPACK_ESP32/bootloader/bootloader.bin /mnt/c/Git/micropython-jpc/
cp /home/w011247/mpbuild/ports/esp32/build-JACKPACK_ESP32/partition_table/partition-table.bin /mnt/c/Git/micropython-jpc/
echo BUILD_COMPLETE
