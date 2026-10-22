//! OS-owned writer locks release on normal exit, interruption, and process crashes.
use std::{
    fs::{File, OpenOptions},
    io::{Seek, SeekFrom, Write},
    path::Path,
};

pub(crate) struct WriterLock {
    _file: File,
}

impl WriterLock {
    pub(crate) fn acquire(path: &Path) -> Result<Self, String> {
        let mut file = OpenOptions::new()
            .read(true)
            .write(true)
            .create(true)
            .truncate(false)
            .open(path)
            .map_err(|e| format!("open cache lock {}: {e}", path.display()))?;
        #[cfg(unix)]
        {
            use std::os::fd::AsRawFd;
            unsafe extern "C" {
                fn flock(
                    fd: std::os::raw::c_int,
                    operation: std::os::raw::c_int,
                ) -> std::os::raw::c_int;
            }
            // LOCK_EX | LOCK_NB has the same values on the supported macOS/Linux hosts.
            if unsafe { flock(file.as_raw_fd(), 2 | 4) } != 0 {
                return Err(format!(
                    "cache already has a writer ({}): {}",
                    path.display(),
                    std::io::Error::last_os_error()
                ));
            }
        }
        #[cfg(not(unix))]
        return Err("cache writer locks require a Unix host".into());
        file.set_len(0).map_err(|e| e.to_string())?;
        file.seek(SeekFrom::Start(0)).map_err(|e| e.to_string())?;
        writeln!(file, "{}", std::process::id()).map_err(|e| e.to_string())?;
        // Keep the inode: unlinking a lock file permits separate locks on old/new inodes.
        Ok(Self { _file: file })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn competing_writer_is_rejected_and_closing_releases_the_lock() {
        let path = std::env::temp_dir().join(format!("pokesim-writer-{}.lock", std::process::id()));
        let first = WriterLock::acquire(&path).unwrap();
        assert!(WriterLock::acquire(&path).is_err());
        drop(first);
        let resumed = WriterLock::acquire(&path).unwrap();
        drop(resumed);
        std::fs::remove_file(path).unwrap();
    }
}
