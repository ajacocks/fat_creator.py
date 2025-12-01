#!/usr/bin/env python3
"""
FAT12/16/32 Filesystem Creator
Creates a FAT12, FAT16, or FAT32 filesystem in a file of specified size.
© 2025 Alexander Jacocks <alexander@redhat.com>
:license: MIT
"""

import struct
import argparse
import math
import subprocess
from datetime import datetime

class Colorcodes(object):
    """
    Copyright © 2012 Martin Ueding <dev@martin-ueding.de>
    Additions © 2025 Alexander Jacocks <alexander@redhat.com>

    Provides ANSI terminal color codes which are gathered via the ``tput``
    utility. That way, they are portable. If there occurs any error with
    ``tput``, all codes are initialized as an empty string.
    The provides fields are listed below.
    Control:
    - bold
    - dim
    - rev
    - reset
    Colors:
    - brightwhite
    - brightcyan
    - brightmagenta
    - brightblue
    - brightyellow
    - brightgreen
    - brightred
    - grey
    - white
    - cyan
    - magenta
    - blue
    - green
    - orange
    - red
    - black
    :license: MIT
    """
    def __init__(self):
        try:
            self.bold = subprocess.check_output("tput bold".split()).decode()
            self.dim = subprocess.check_output("tput dim".split()).decode()
            self.rev = subprocess.check_output("tput rev".split()).decode()
            self.reset = subprocess.check_output("tput sgr0".split()).decode()

            self.brightwhite = subprocess.check_output("tput setaf 15".split()).decode()
            self.brightcyan = subprocess.check_output("tput setaf 14".split()).decode()
            self.brightmagenta = subprocess.check_output("tput setaf 13".split()).decode()
            self.brightblue = subprocess.check_output("tput setaf 12".split()).decode()
            self.brightyellow = subprocess.check_output("tput setaf 11".split()).decode()
            self.brightgreen = subprocess.check_output("tput setaf 10".split()).decode()
            self.brightred = subprocess.check_output("tput setaf 9".split()).decode()
            self.grey = subprocess.check_output("tput setaf 8".split()).decode()
            self.white = subprocess.check_output("tput setaf 7".split()).decode()
            self.cyan = subprocess.check_output("tput setaf 6".split()).decode()
            self.magenta = subprocess.check_output("tput setaf 5".split()).decode()
            self.blue = subprocess.check_output("tput setaf 4".split()).decode()
            self.green = subprocess.check_output("tput setaf 2".split()).decode()
            self.orange = subprocess.check_output("tput setaf 3".split()).decode()
            self.red = subprocess.check_output("tput setaf 1".split()).decode()
            self.black = subprocess.check_output("tput setaf 0".split()).decode()
        except subprocess.CalledProcessError as e:
            self.bold = ""
            self.dim = ""
            self.rev = ""
            self.reset = ""

            self.white = ""
            self.cyan = ""
            self.magenta = ""
            self.blue = ""
            self.green = ""
            self.orange = ""
            self.red = ""
            self.black = ""

class FATCreator:
        
    def __init__(self, size_kb, fat_type=None, volume_label="NO NAME"):
        
        self.size_kb = size_kb
        self.size_bytes = size_kb * 1024
        self.size_mb = size_kb / 1024

        self.volume_label = volume_label[:11].ljust(11)  # Max 11 chars
        
        self.fat_type = fat_type
        
        # Constants
        self.bytes_per_sector = 512
        self.reserved_sectors = 32 if fat_type == "FAT32" else 1
        self.num_fats = 2
        # FAT32 has no root directory in reserved area, FAT12/16 do
        self.root_entries = 0 if fat_type == "FAT32" else (512 if fat_type != "FAT12" else 224)
        self.media_descriptor = 0xF8  # Fixed disk
        
        # Calculate filesystem parameters
        self._calculate_parameters()
        
    def _calculate_parameters(self):
        """Calculate FAT filesystem parameters based on size"""
        total_sectors = self.size_bytes // self.bytes_per_sector
        
        # Determine sectors per cluster based on disk size
        # These are Microsoft's recommended values
        if self.fat_type == "FAT32":
            # FAT32 cluster sizes
            if self.size_mb < 260:
                self.sectors_per_cluster = 1  # 512 bytes
            elif self.size_mb < 8192:
                self.sectors_per_cluster = 8  # 4 KB
            elif self.size_mb < 16384:
                self.sectors_per_cluster = 16  # 8 KB
            elif self.size_mb < 32768:
                self.sectors_per_cluster = 32  # 16 KB
            else:
                self.sectors_per_cluster = 64  # 32 KB
        else:
            # FAT12/16 cluster sizes
            if self.size_mb <= 8:
                self.sectors_per_cluster = 1
            elif self.size_mb <= 32:
                self.sectors_per_cluster = 2
            elif self.size_mb <= 64:
                self.sectors_per_cluster = 4
            elif self.size_mb <= 128:
                self.sectors_per_cluster = 8
            elif self.size_mb <= 256:
                self.sectors_per_cluster = 16
            elif self.size_mb <= 512:
                self.sectors_per_cluster = 32
            else:
                self.sectors_per_cluster = 64
            
        # Calculate root directory size in sectors (0 for FAT32)
        self.root_dir_sectors = ((self.root_entries * 32) + 
                                 (self.bytes_per_sector - 1)) // self.bytes_per_sector
        
        # Calculate FAT size
        # This is an iterative process since FAT size depends on data clusters
        self.sectors_per_fat = self._calculate_fat_size(total_sectors)
        
        # Calculate data region start
        self.data_start_sector = (self.reserved_sectors + 
                                  (self.num_fats * self.sectors_per_fat) + 
                                  self.root_dir_sectors)
        
        # Calculate total data sectors and clusters
        self.data_sectors = total_sectors - self.data_start_sector
        self.total_clusters = self.data_sectors // self.sectors_per_cluster
        
        # Auto-detect FAT type if not specified
        if self.fat_type is None:
            if self.total_clusters < 4085:
                self.fat_type = "FAT12"
                # Recalculate with proper parameters for FAT12
                self.reserved_sectors = 1
                self.root_entries = 224
                self._calculate_parameters()
                return
            elif self.total_clusters < 65525:
                self.fat_type = "FAT16"
                # Recalculate with proper parameters for FAT16
                self.reserved_sectors = 1
                self.root_entries = 512
                self._calculate_parameters()
                return
            else:
                self.fat_type = "FAT32"
                # Recalculate with proper parameters for FAT32
                self.reserved_sectors = 32
                self.root_entries = 0
                self._calculate_parameters()
                return
        
        # Validate FAT type
        if self.fat_type == "FAT12" and self.total_clusters >= 4085:
            raise ValueError("Too many clusters for FAT12")
        elif self.fat_type == "FAT16" and self.total_clusters >= 65525:
            raise ValueError("Too many clusters for FAT16")
        elif self.fat_type == "FAT16" and self.total_clusters < 4085:
            raise ValueError("Too few clusters for FAT16 (use FAT12)")
        elif self.fat_type == "FAT32" and self.total_clusters < 65525:
            raise ValueError("Too few clusters for FAT32 (use FAT16)")
            
        # For FAT32, set root cluster
        if self.fat_type == "FAT32":
            self.root_cluster = 2  # Root directory starts at cluster 2
            
    def _calculate_fat_size(self, total_sectors):
        """Calculate the number of sectors needed for one FAT"""
        # Start with an estimate
        temp_fat_size = 1
        
        for _ in range(10):  # Iterate to converge on correct size
            data_start = (self.reserved_sectors + 
                         (self.num_fats * temp_fat_size) + 
                         self.root_dir_sectors)
            data_sectors = total_sectors - data_start
            clusters = data_sectors // self.sectors_per_cluster
            
            # Determine FAT type for calculation
            if self.fat_type == "FAT12" or (self.fat_type is None and clusters < 4085):
                # FAT12: 1.5 bytes per entry
                fat_bytes = math.ceil((clusters + 2) * 1.5)
            elif self.fat_type == "FAT32" or (self.fat_type is None and clusters >= 65525):
                # FAT32: 4 bytes per entry
                fat_bytes = (clusters + 2) * 4
            else:
                # FAT16: 2 bytes per entry
                fat_bytes = (clusters + 2) * 2
                
            temp_fat_size = (fat_bytes + self.bytes_per_sector - 1) // self.bytes_per_sector
            
        return temp_fat_size
    
    def _create_boot_sector(self):
        """Create the boot sector (including BPB)"""
        boot_sector = bytearray(512)
        
        # Jump instruction
        boot_sector[0:3] = b'\xEB\x3C\x90'
        
        # OEM name
        boot_sector[3:11] = b'PYTHON3'
        
        # BIOS Parameter Block (BPB) - Common to all FAT types
        struct.pack_into('<H', boot_sector, 11, self.bytes_per_sector)  # Bytes per sector
        struct.pack_into('<B', boot_sector, 13, self.sectors_per_cluster)  # Sectors per cluster
        struct.pack_into('<H', boot_sector, 14, self.reserved_sectors)  # Reserved sectors
        struct.pack_into('<B', boot_sector, 16, self.num_fats)  # Number of FATs
        struct.pack_into('<H', boot_sector, 17, self.root_entries)  # Root entries (0 for FAT32)
        
        # Total sectors (16-bit) - used for FAT12/16 if < 65536 sectors
        total_sectors = self.size_bytes // self.bytes_per_sector
        if total_sectors < 65536 and self.fat_type != "FAT32":
            struct.pack_into('<H', boot_sector, 19, total_sectors)
        else:
            struct.pack_into('<H', boot_sector, 19, 0)
            
        struct.pack_into('<B', boot_sector, 21, self.media_descriptor)  # Media descriptor
        
        # Sectors per FAT (16-bit) - 0 for FAT32
        if self.fat_type == "FAT32":
            struct.pack_into('<H', boot_sector, 22, 0)
        else:
            struct.pack_into('<H', boot_sector, 22, self.sectors_per_fat)
            
        struct.pack_into('<H', boot_sector, 24, 63)  # Sectors per track
        struct.pack_into('<H', boot_sector, 26, 255)  # Number of heads
        struct.pack_into('<I', boot_sector, 28, 0)  # Hidden sectors
        
        # Total sectors (32-bit)
        if total_sectors >= 65536 or self.fat_type == "FAT32":
            struct.pack_into('<I', boot_sector, 32, total_sectors)
        else:
            struct.pack_into('<I', boot_sector, 32, 0)
        
        if self.fat_type == "FAT32":
            # FAT32 Extended BPB
            struct.pack_into('<I', boot_sector, 36, self.sectors_per_fat)  # Sectors per FAT (32-bit)
            struct.pack_into('<H', boot_sector, 40, 0)  # Extended flags
            struct.pack_into('<H', boot_sector, 42, 0)  # Filesystem version
            struct.pack_into('<I', boot_sector, 44, self.root_cluster)  # Root directory cluster
            struct.pack_into('<H', boot_sector, 48, 1)  # FSInfo sector
            struct.pack_into('<H', boot_sector, 50, 6)  # Backup boot sector
            # Reserved bytes 52-63 are already zero
            
            struct.pack_into('<B', boot_sector, 64, 0x80)  # Drive number
            struct.pack_into('<B', boot_sector, 65, 0)  # Reserved
            struct.pack_into('<B', boot_sector, 66, 0x29)  # Extended boot signature
            
            # Volume serial number
            serial = int(datetime.now().timestamp()) & 0xFFFFFFFF
            struct.pack_into('<I', boot_sector, 67, serial)
            
            # Volume label
            boot_sector[71:82] = self.volume_label.encode('ascii')
            
            # Filesystem type
            boot_sector[82:90] = b'FAT32   '
        else:
            # FAT12/16 Extended BPB
            struct.pack_into('<B', boot_sector, 36, 0x80)  # Drive number
            struct.pack_into('<B', boot_sector, 37, 0)  # Reserved
            struct.pack_into('<B', boot_sector, 38, 0x29)  # Extended boot signature
            
            # Volume serial number (based on current time)
            serial = int(datetime.now().timestamp()) & 0xFFFFFFFF
            struct.pack_into('<I', boot_sector, 39, serial)
            
            # Volume label
            boot_sector[43:54] = self.volume_label.encode('ascii')
            
            # Filesystem type
            fs_type = f"{self.fat_type}   ".encode('ascii')
            boot_sector[54:62] = fs_type
        
        # Boot signature
        boot_sector[510:512] = b'\x55\xAA'
        
        return bytes(boot_sector)
    
    def _create_fat(self):
        """Create the File Allocation Table"""
        fat_size_bytes = self.sectors_per_fat * self.bytes_per_sector
        fat = bytearray(fat_size_bytes)
        
        if self.fat_type == "FAT12":
            # First two entries: media descriptor and EOF
            # FAT12 uses 12 bits per entry, stored in a special format
            fat[0] = self.media_descriptor
            fat[1] = 0xFF
            fat[2] = 0xFF
        elif self.fat_type == "FAT16":
            # First entry: media descriptor in low byte, 0xFF in high byte
            struct.pack_into('<H', fat, 0, 0xFF00 | self.media_descriptor)
            # Second entry: EOF marker
            struct.pack_into('<H', fat, 2, 0xFFFF)
        else:  # FAT32
            # First entry: media descriptor in low byte, rest 0x0FFFFF
            struct.pack_into('<I', fat, 0, 0x0FFFFF00 | self.media_descriptor)
            # Second entry: EOF marker / clean shutdown marker
            struct.pack_into('<I', fat, 4, 0x0FFFFFFF)
            # Third entry: end of chain for root directory
            struct.pack_into('<I', fat, 8, 0x0FFFFFFF)
            
        return bytes(fat)
    
    def _create_root_directory(self):
        """Create an empty root directory"""
        if self.fat_type == "FAT32":
            # FAT32 root directory is in the data area (one cluster)
            root_size = self.sectors_per_cluster * self.bytes_per_sector
        else:
            root_size = self.root_dir_sectors * self.bytes_per_sector
            
        root_dir = bytearray(root_size)
        
        # Optionally add volume label entry
        if self.volume_label.strip():
            # Volume label entry (first entry in root directory)
            root_dir[0:11] = self.volume_label.encode('ascii')
            root_dir[11] = 0x08  # Volume label attribute
            
        return bytes(root_dir)
    
    def _create_fsinfo(self):
        """Create FSInfo sector for FAT32"""
        fsinfo = bytearray(512)
        
        # Lead signature
        struct.pack_into('<I', fsinfo, 0, 0x41615252)
        
        # Structure signature
        struct.pack_into('<I', fsinfo, 484, 0x61417272)
        
        # Free cluster count (unknown/uncalculated = 0xFFFFFFFF)
        struct.pack_into('<I', fsinfo, 488, self.total_clusters - 1)
        
        # Next free cluster (start search at cluster 3, after root)
        struct.pack_into('<I', fsinfo, 492, 3)
        
        # Trail signature
        struct.pack_into('<I', fsinfo, 508, 0xAA550000)
        
        return bytes(fsinfo)
    
    def create_filesystem(self, filename):
        """Create the FAT filesystem and write to file"""
        colors = Colorcodes()
        print(f"{colors.bold}{colors.brightcyan}Creating {self.fat_type} filesystem in file {colors.orange}{filename}:{colors.reset}")
        print(f"  {colors.green}Size: {colors.orange}{self.size_mb} MiB ({self.size_kb} KiB, {self.size_bytes} bytes)")
        print(f"  {colors.green}Sectors per cluster: {colors.orange}{self.sectors_per_cluster}")
        print(f"  {colors.green}Total clusters: {colors.orange}{self.total_clusters}")
        print(f"  {colors.green}Sectors per FAT: {colors.orange}{self.sectors_per_fat}")
        if self.fat_type == "FAT32":
            print(f"  {colors.green}Root directory cluster: {colors.orange}{self.root_cluster}")
        else:
            print(f"  {colors.green}Root directory entries: {colors.orange}{self.root_entries}")
        
        try:
            with open(filename, 'wb') as f:
                # Write boot sector
                f.write(self._create_boot_sector())
                
                if self.fat_type == "FAT32":
                    # Write FSInfo sector (sector 1)
                    f.write(self._create_fsinfo())
                    
                    # Write remaining reserved sectors up to backup boot sector
                    for _ in range(self.reserved_sectors - 7):  # -7 for boot, fsinfo, and 5 before backup
                        f.write(b'\x00' * self.bytes_per_sector)
                    
                    # Write backup boot sector (sector 6)
                    f.write(self._create_boot_sector())
                    
                    # Write backup FSInfo sector
                    f.write(self._create_fsinfo())
                    
                    # Write remaining reserved sectors
                    for _ in range(4):  # Remaining reserved sectors after backup
                        f.write(b'\x00' * self.bytes_per_sector)
                else:
                    # Write reserved sectors (if any beyond boot sector) for FAT12/16
                    for _ in range(self.reserved_sectors - 1):
                        f.write(b'\x00' * self.bytes_per_sector)
                
                # Write FATs
                fat_data = self._create_fat()
                for _ in range(self.num_fats):
                    f.write(fat_data)
                
                if self.fat_type == "FAT32":
                    # For FAT32, root directory is in data area
                    # Write data region
                    data_size = self.data_sectors * self.bytes_per_sector
                    
                    # First cluster (cluster 2) is the root directory
                    root_data = self._create_root_directory()
                    f.write(root_data)
                    
                    # Write remaining data area
                    remaining = data_size - len(root_data)
                    chunk_size = 1024 * 1024  # Write 1MB at a time
                    
                    while remaining > 0:
                        write_size = min(chunk_size, remaining)
                        f.write(b'\x00' * write_size)
                        remaining -= write_size
                else:
                    # For FAT12/16, write root directory then data area
                    f.write(self._create_root_directory())
                    
                    # Write data region (all zeros)
                    data_size = self.data_sectors * self.bytes_per_sector
                    chunk_size = 1024 * 1024  # Write 1MB at a time
                    remaining = data_size
                    
                    while remaining > 0:
                        write_size = min(chunk_size, remaining)
                        f.write(b'\x00' * write_size)
                        remaining -= write_size
        except:
            print(f"{colors.bold}{colors.brightred}Failed to open file {colors.orange}{filename}{colors.brightred}!")
            exit()

        print(f"\n{colors.bold}{colors.brightcyan}Filesystem created successfully: {colors.orange}{filename}")

def switch(disk):
    if disk == "525dd":
        return 360
    elif disk == "525hd":
        return 1200
    elif disk == "35dd":
        return 720
    elif disk == "35hd":
        return 1440
    elif disk == "35ed":
        return 2880

def main():
    colors = Colorcodes()
    # numcolors = subprocess.check_output("tput colors".split())
    # print("Terminal has "+numcolors.decode().rstrip()+" colors.")
    epilog = f"""
{colors.bold}{colors.brightblue}examples:
  {colors.brightred}# create a 1.44MiB volume in the file floppy.img
  {colors.magenta}%(prog)s {colors.green}-D {colors.orange}35hd {colors.orange}floppy.img
  {colors.brightred}# create a 360KiB volume in the file floppy.img
  {colors.magenta}%(prog)s {colors.green}-D {colors.orange}525dd {colors.orange}floppy.img
  {colors.brightred}# create a 10MiB FAT16 volume in the file disk.img
  {colors.magenta}%(prog)s {colors.green}-s {colors.orange}10240 {colors.green}-t {colors.orange}FAT16 disk.img
  {colors.brightred}# create a 2MiB FAT12 volume with the label \"MY DISK\" in the file floppy.img
  {colors.magenta}%(prog)s {colors.green}-s {colors.orange}2048 {colors.green}-t {colors.orange}FAT12 {colors.green}-l {colors.orange}\"MY DISK\" floppy.img
  {colors.brightred}# create a 512MiB FAT32 volume in the file bigdisk.img
  {colors.magenta}%(prog)s {colors.green}-s {colors.orange}564288 {colors.green}-t {colors.orange}FAT32 bigdisk.img
  {colors.brightred}# create a 100MiB volume, FAT size autodetected, in the file disk.img
  {colors.magenta}%(prog)s {colors.green}-s {colors.orange}102400 disk.img{colors.reset}
    """
    parser = argparse.ArgumentParser(
        description=f"{colors.cyan}{colors.bold}Create FAT12, FAT16, or FAT32 filesystem in a file",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=epilog
    )
    
    parser.add_argument('-s', '--size', type=int,
                       help='Size in kilobytes (KB)')
    parser.add_argument('-D', '--disk', choices=['525dd', '525hd', '35dd', '35hd', '35ed'], type=str.lower, 
                        help='Disk type (5.25 dd, 5.25 hd, 3.5 dd, 3.5 hd, or 3.5 ed)')
    parser.add_argument('-t', '--type', choices=['fat12', 'fat16', 'fat32'], type=str.lower,
                       help='FAT type (auto-detected if not specified)')
    parser.add_argument('-l', '--label', default='NO NAME', type=str.upper,
                       help='Volume label (max 11 characters)')
    parser.add_argument('output', help='Output file name')
    
    args = parser.parse_args()
    
    if args.size is None and args.disk is None:
        parser.error("Either --disk|-D or --size|-S is required.")
    elif args.size is None:
        args.size=switch(args.disk)
    try:
        creator = FATCreator(args.size, args.type, args.label)
        creator.create_filesystem(args.output)
    except ValueError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}")
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())
