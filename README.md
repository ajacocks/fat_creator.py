    # fat_creator.py
    This is a Python script created to ease FAT disk image creation on Mac OS, where you otherwise have to create the file, mount it, and then format it.
    
    usage: fat_creator.py [-h] [-s SIZE] [-D {525dd,525hd,35dd,35hd,35ed}]
                          [-t {fat12,fat16,fat32}] [-l LABEL]
                          output
    
    Create FAT12, FAT16, or FAT32 filesystem in a file
    
    positional arguments:
      output                Output file name
    
    options:
      -h, --help            show this help message and exit
      -s, --size SIZE       Size in kilobytes (KB)
      -D, --disk {525dd,525hd,35dd,35hd,35ed}
                            Disk type (5.25 dd, 5.25 hd, 3.5 dd, 3.5 hd, or 3.5
                            ed)
      -t, --type {fat12,fat16,fat32}
                            FAT type (auto-detected if not specified)
      -l, --label LABEL     Volume label (max 11 characters)
    
    examples:
      # create a 1.44MiB volume in the file floppy.img
      /Users/ajacocks/src/./fat_creator.py -D 35hd floppy.img
      # create a 360KiB volume in the file floppy.img
      fat_creator.py -D 525dd floppy.img
      # create a 10MiB FAT16 volume in the file disk.img
      fat_creator.py -s 10240 -t FAT16 disk.img
      # create a 2MiB FAT12 volume with the label "MY DISK" in the file floppy.img
      fat_creator.py -s 2048 -t FAT12 -l "MY DISK" floppy.img
      # create a 512MiB FAT32 volume in the file bigdisk.img
      fat_creator.py -s 564288 -t FAT32 bigdisk.img
      # create a 100MiB volume, FAT size autodetected, in the file disk.img
      fat_creator.py -s 102400 disk.img
