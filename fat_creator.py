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
import os
from datetime import datetime
from pathlib import Path

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
            self.italic = subprocess.check_output("tput sitm".split()).decode()
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
            self.italic = ""
            self.reset = ""

            self.brightwhite = ""
            self.brightcyan = ""
            self.brightmagenta = ""
            self.brightblue = ""
            self.brightyellow = ""
            self.brightgreen = ""
            self.brightred = ""
            self.grey = ""
            self.white = ""
            self.cyan = ""
            self.magenta = ""
            self.blue = ""
            self.green = ""
            self.orange = ""
            self.red = ""
            self.black = ""

class FATCreator:
        
    def __init__(self, size_kb, fat_type=None, volume_label="NO NAME", files_to_add=None):
        
        self.size_kb = size_kb
        self.size_bytes = size_kb * 1024
        self.size_mb = size_kb / 1024

        self.volume_label = volume_label[:11].ljust(11)  # Max 11 chars
        
        self.fat_type = fat_type
        self.files_to_add = files_to_add or []

        # Constants
        self.bytes_per_sector = 512
        self.reserved_sectors = 32 if fat_type == "FAT32" else 1
        self.num_fats = 2
        # FAT32 has no root directory in reserved area, FAT12/16 do
        self.root_entries = 0 if fat_type == "FAT32" else (512 if fat_type != "FAT12" else 224)
        self.media_descriptor = 0xF8  # Fixed disk
        
        # Calculate filesystem parameters
        self._calculate_parameters()

        # Initialize FAT in memory for file allocation
        self.fat_entries = [0] * (self.total_clusters + 2)
        
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
            # Initialize with media descriptor and EOF
            self.fat_entries[0] = 0xFF0 | self.media_descriptor
            self.fat_entries[1] = 0xFFF

            # Write FAT12 entries (1.5 bytes per entry)
            for i in range(len(self.fat_entries)):
                if i % 2 == 0:  # Even entry
                    byte_offset = (i * 3) // 2
                    if byte_offset + 1 < fat_size_bytes:
                        fat[byte_offset] = self.fat_entries[i] & 0xFF
                        fat[byte_offset + 1] = (fat[byte_offset + 1] & 0xF0) | ((self.fat_entries[i] >> 8) & 0x0F)
                else:  # Odd entry
                    byte_offset = (i * 3) // 2
                    if byte_offset + 1 < fat_size_bytes:
                        fat[byte_offset] = (fat[byte_offset] & 0x0F) | ((self.fat_entries[i] & 0x0F) << 4)
                        fat[byte_offset + 1] = (self.fat_entries[i] >> 4) & 0xFF
    
        elif self.fat_type == "FAT16":
            # Initialize with media descriptor and EOF
            self.fat_entries[0] = 0xFF00 | self.media_descriptor
            self.fat_entries[1] = 0xFFFF

            # Write FAT16 entries (2 bytes per entry)
            for i in range(len(self.fat_entries)):
                offset = i * 2
                if offset + 1 < fat_size_bytes:
                    struct.pack_into('<H', fat, offset, self.fat_entries[i] & 0xFFFF)

        else:  # FAT32
            # Initialize with media descriptor, EOF, and root directory chain
            self.fat_entries[0] = 0x0FFFFF00 | self.media_descriptor
            self.fat_entries[1] = 0x0FFFFFFF
            self.fat_entries[2] = 0x0FFFFFFF  # Root directory end marker

            # Write FAT32 entries (4 bytes per entry, only lower 28 bits used)
            for i in range(len(self.fat_entries)):
                offset = i * 4
                if offset + 3 < fat_size_bytes:
                    struct.pack_into('<I', fat, offset, self.fat_entries[i] & 0x0FFFFFFF)
            
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

    def _allocate_clusters(self, num_clusters):
        """Allocate a chain of clusters and return the first cluster number"""
        if num_clusters == 0:
            return 0

        # Find first free cluster (starting from 2 or 3 for FAT32)
        start_cluster = 3 if self.fat_type == "FAT32" else 2
        first_cluster = None
        prev_cluster = None
        allocated = 0

        for cluster in range(start_cluster, self.total_clusters + 2):
            if self.fat_entries[cluster] == 0:  # Free cluster
                if first_cluster is None:
                    first_cluster = cluster

                if prev_cluster is not None:
                    self.fat_entries[prev_cluster] = cluster

                prev_cluster = cluster
                allocated += 1

                if allocated == num_clusters:
                    # Mark end of chain
                    if self.fat_type == "FAT12":
                        self.fat_entries[cluster] = 0xFFF
                    elif self.fat_type == "FAT16":
                        self.fat_entries[cluster] = 0xFFFF
                    else:  # FAT32
                        self.fat_entries[cluster] = 0x0FFFFFFF
                    return first_cluster

        raise ValueError(f"Not enough free clusters (needed {num_clusters}, found {allocated})")

    def _make_8_3_name(self, filename):
        """Convert filename to 8.3 format (8 char name + 3 char extension)"""
        name, ext = os.path.splitext(filename)

        # Remove leading dot if present
        if ext.startswith('.'):
            ext = ext[1:]

        # Truncate and pad name
        name = name[:8].upper().ljust(8)
        ext = ext[:3].upper().ljust(3)

        return (name + ext).encode('ascii')

    def _create_directory_entry(self, filename, file_size, first_cluster, is_directory=False):
        """Create a 32-byte directory entry"""
        entry = bytearray(32)

        # Filename (8.3 format)
        entry[0:11] = self._make_8_3_name(filename)

        # Attributes
        attr = 0x20  # Archive
        if is_directory:
            attr = 0x10  # Directory
        entry[11] = attr

        # Reserved / creation time fine resolution
        entry[12] = 0

        # Creation time and date (use current time)
        now = datetime.now()
        time_val = ((now.hour << 11) | (now.minute << 5) | (now.second // 2))
        date_val = (((now.year - 1980) << 9) | (now.month << 5) | now.day)

        struct.pack_into('<H', entry, 14, time_val)  # Creation time
        struct.pack_into('<H', entry, 16, date_val)  # Creation date
        struct.pack_into('<H', entry, 18, date_val)  # Last access date

        # High word of first cluster (FAT32)
        if self.fat_type == "FAT32":
            struct.pack_into('<H', entry, 20, (first_cluster >> 16) & 0xFFFF)
        else:
            struct.pack_into('<H', entry, 20, 0)

        # Last modification time and date
        struct.pack_into('<H', entry, 22, time_val)
        struct.pack_into('<H', entry, 24, date_val)

        # Low word of first cluster
        struct.pack_into('<H', entry, 26, first_cluster & 0xFFFF)

        # File size
        struct.pack_into('<I', entry, 28, file_size)

        return bytes(entry)

    def _add_files_to_root(self, root_dir):
        """Add file entries to root directory and return updated root + file data"""
        colors = Colorcodes()
        root_dir = bytearray(root_dir)
        file_data_map = {}  # Maps cluster number to file data

        # Find first free entry in root directory (skip volume label if present)
        entry_offset = 32 if self.volume_label.strip() else 0

        for file_path in self.files_to_add:
            if not os.path.exists(file_path):
                print(f"Warning: File not found: {file_path}")
                continue

            # Read file content
            with open(file_path, 'rb') as f:
                file_content = f.read()

            file_size = len(file_content)
            filename = os.path.basename(file_path)

            # Calculate clusters needed
            bytes_per_cluster = self.sectors_per_cluster * self.bytes_per_sector
            clusters_needed = (file_size + bytes_per_cluster - 1) // bytes_per_cluster

            if clusters_needed == 0:
                clusters_needed = 1  # Minimum 1 cluster even for empty files

            # Allocate clusters
            try:
                first_cluster = self._allocate_clusters(clusters_needed)
            except ValueError as e:
                print(f"Warning: Cannot add {filename}: {e}")
                continue

            # Create directory entry
            dir_entry = self._create_directory_entry(filename, file_size, first_cluster)

            # Check if we have space in root directory
            if self.fat_type == "FAT32":
                root_size = self.sectors_per_cluster * self.bytes_per_sector
            else:
                root_size = self.root_dir_sectors * self.bytes_per_sector

            if entry_offset + 32 > root_size:
                print(f"Warning: Root directory full, cannot add {filename}")
                break

            # Add entry to root directory
            root_dir[entry_offset:entry_offset + 32] = dir_entry
            entry_offset += 32

            # Store file data mapped to clusters
            cluster = first_cluster
            offset = 0

            while offset < file_size and cluster < self.total_clusters + 2:
                chunk_size = min(bytes_per_cluster, file_size - offset)
                chunk_data = file_content[offset:offset + chunk_size]

                # Pad cluster to full size
                chunk_data = chunk_data + (b'\x00' * (bytes_per_cluster - len(chunk_data)))
                file_data_map[cluster] = chunk_data

                offset += chunk_size

                # Get next cluster in chain
                if self.fat_type == "FAT12":
                    next_cluster = self.fat_entries[cluster]
                    if next_cluster >= 0xFF8:
                        break
                elif self.fat_type == "FAT16":
                    next_cluster = self.fat_entries[cluster]
                    if next_cluster >= 0xFFF8:
                        break
                else:  # FAT32
                    next_cluster = self.fat_entries[cluster]
                    if next_cluster >= 0x0FFFFFF8:
                        break

                cluster = next_cluster

            print(f"  {colors.green}Added: {colors.orange}{filename} {colors.green}({colors.orange}{file_size} {colors.green}bytes, {colors.orange}{clusters_needed} {colors.green}clusters)")

        return bytes(root_dir), file_data_map

    def create_filesystem(self, filename):
        """Create the FAT filesystem and write to file"""
        colors = Colorcodes()
        print(f"{colors.bold}{colors.brightcyan}Creating {self.fat_type} filesystem in file {colors.orange}{filename}:{colors.reset}")
        print(f"  {colors.green}Size: {colors.orange}{self.size_mb} MiB ({self.size_kb} KiB, {self.size_bytes} bytes)")
        print(f". {colors.green}FAT type: {colors.orange}{self.fat_type}")
        print(f"  {colors.green}Sectors per cluster: {colors.orange}{self.sectors_per_cluster}")
        print(f"  {colors.green}Total clusters: {colors.orange}{self.total_clusters}")
        print(f"  {colors.green}Sectors per FAT: {colors.orange}{self.sectors_per_fat}")
        if self.fat_type == "FAT32":
            print(f"  {colors.green}Root directory cluster: {colors.orange}{self.root_cluster}")
        else:
            print(f"  {colors.green}Root directory entries: {colors.orange}{self.root_entries}")

        # Prepare root directory and file data
        root_dir_data = self._create_root_directory()
        file_data_map = {}

        if self.files_to_add:
            print(f"\n{colors.bold}{colors.brightcyan}Adding files:{colors.reset}")
            root_dir_data, file_data_map = self._add_files_to_root(root_dir_data)

        # Create FAT with allocated clusters
        fat_data = self._create_fat()

        try:
            with open(filename, 'wb') as f:
                # Write boot sector
                f.write(self._create_boot_sector())

                if self.fat_type == "FAT32":
                    # Write FSInfo sector (sector 1)
                    f.write(self._create_fsinfo())

                    # Write sectors 2-5 (4 sectors)
                    for _ in range(4):
                        f.write(b'\x00' * self.bytes_per_sector)

                    # Write backup boot sector (sector 6)
                    f.write(self._create_boot_sector())

                    # Write backup FSInfo sector (sector 7)
                    f.write(self._create_fsinfo())

                    # Write remaining reserved sectors (8-31, which is 24 sectors)
                    for _ in range(self.reserved_sectors - 8):
                        f.write(b'\x00' * self.bytes_per_sector)
                else:
                    # Write reserved sectors (if any beyond boot sector) for FAT12/16
                    for _ in range(self.reserved_sectors - 1):
                        f.write(b'\x00' * self.bytes_per_sector)

                # Write FATs
                for _ in range(self.num_fats):
                    f.write(fat_data)

                if self.fat_type == "FAT32":
                    # For FAT32, root directory is in data area
                    # Calculate data region size
                    bytes_per_cluster = self.sectors_per_cluster * self.bytes_per_sector

                    # Write cluster 2 (root directory)
                    f.write(root_dir_data)

                    # Write remaining clusters
                    for cluster_num in range(3, self.total_clusters + 2):
                        if cluster_num in file_data_map:
                            f.write(file_data_map[cluster_num])
                        else:
                            f.write(b'\x00' * bytes_per_cluster)
                else:
                    # For FAT12/16, write root directory then data area
                    f.write(root_dir_data)

                    # Write data region
                    bytes_per_cluster = self.sectors_per_cluster * self.bytes_per_sector

                    for cluster_num in range(2, self.total_clusters + 2):
                        if cluster_num in file_data_map:
                            f.write(file_data_map[cluster_num])
                        else:
                            f.write(b'\x00' * bytes_per_cluster)

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
    epilog = f"""
{colors.bold}{colors.brightblue}examples:
  {colors.brightred}# create a 1.44MiB volume in the file floppy.img
  {colors.magenta}%(prog)s {colors.green}-D {colors.orange}35hd {colors.orange} {colors.green}-o {colors.orange}floppy.img
  {colors.brightred}# create a 360KiB volume in the file floppy.img
  {colors.magenta}%(prog)s {colors.green}-D {colors.orange}525dd {colors.orange}-o {colors.orange}floppy.img
  {colors.brightred}# create a 10MiB FAT16 volume in the file disk.img
  {colors.magenta}%(prog)s {colors.green}-s {colors.orange}10240 {colors.green}-t {colors.orange}FAT16 {colors.green}-o {colors.orange}disk.img
  {colors.brightred}# create a 2MiB FAT12 volume with the label \"MY DISK\" in the file floppy.img
  {colors.magenta}%(prog)s {colors.green}-s {colors.orange}2048 {colors.green}-t {colors.orange}FAT12 {colors.green}-l {colors.orange}\"MY DISK\" {colors.green}-o {colors.orange}floppy.img
  {colors.brightred}# create a 512MiB FAT32 volume in the file bigdisk.img
  {colors.magenta}%(prog)s {colors.green}-s {colors.orange}564288 {colors.green}-t {colors.orange}FAT32 {colors.green}-o {colors.orange}bigdisk.img
  {colors.brightred}# create a 100MiB volume, FAT size autodetected, in the file disk.img
  {colors.magenta}%(prog)s {colors.green}-s {colors.orange}102400 {colors.green}-o {colors.orange}disk.img
  {colors.brightred}# create a 10MiB FAT16 volume, with the files file1.txt and file2.bin, in the file disk.img
  {colors.magenta}%(prog)s {colors.green}-s {colors.orange}10240 {colors.green}-t {colors.orange}FAT16 {colors.green}-o {colors.orange}disk.img {colors.green}-f {colors.orange}file1.txt file2.bin 
  {colors.brightred}# create a 50MiB FAT16 volume, FAT size autodetected, with the files file1.txt and file2.bin, in the file disk.img
  {colors.magenta}%(prog)s {colors.green}-s {colors.orange}51200 {colors.green}-o {colors.orange}disk.img {colors.green}-f {colors.orange}*.txt{colors.reset}
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
    parser.add_argument('-t', '--type', choices=['FAT12', 'FAT16', 'FAT32'], type=str.upper,
                       help='FAT type (auto-detected if not specified)')
    parser.add_argument('-l', '--label', default='NO NAME', type=str.upper,
                       help='Volume label (max 11 characters)')
    parser.add_argument('-f', '--files', nargs='+', default=[],
                       help='Files to add to the filesystem')
    parser.add_argument('-o', '--output', help='Output file name', required=True)
    
    args = parser.parse_args()
    
    if args.size is None and args.disk is None:
        parser.error("Either --disk|-D or --size|-S is required.")
    elif args.size is None:
        args.size=switch(args.disk)
    try:
        creator = FATCreator(args.size, args.type, args.label, args.files)
        creator.create_filesystem(args.output)
    except ValueError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())
