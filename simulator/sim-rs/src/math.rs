use std::cell::Cell;

/// Every transcendental call the engine makes goes through this trait, in the
/// same order as sim/match.js, so a recorded JS trace can be replayed.
pub trait MathFns {
    fn sin(&self, x: f64) -> f64;
    fn cos(&self, x: f64) -> f64;
    fn atan2(&self, y: f64, x: f64) -> f64;
    fn pow(&self, x: f64, y: f64) -> f64;
}

pub struct Libm;

impl MathFns for Libm {
    #[inline]
    fn sin(&self, x: f64) -> f64 {
        libm::sin(x)
    }
    #[inline]
    fn cos(&self, x: f64) -> f64 {
        libm::cos(x)
    }
    #[inline]
    fn atan2(&self, y: f64, x: f64) -> f64 {
        libm::atan2(y, x)
    }
    #[inline]
    fn pow(&self, x: f64, y: f64) -> f64 {
        libm::pow(x, y)
    }
}

/// Replays a trace of `[fn, a, b, out]` records written by sim-rs/parity.js.
/// Panics at the first call whose function or inputs differ from the trace.
pub struct Replay {
    log: Vec<f64>,
    at: Cell<usize>,
}

const SIN: f64 = 1.0;
const COS: f64 = 2.0;
const ATAN2: f64 = 3.0;
const POW: f64 = 4.0;

impl Replay {
    pub fn new(log: Vec<f64>) -> Self {
        Replay { log, at: Cell::new(0) }
    }

    pub fn consumed_all(&self) -> bool {
        self.at.get() * 4 == self.log.len()
    }

    pub fn calls(&self) -> usize {
        self.at.get()
    }

    fn take(&self, f: f64, a: f64, b: f64) -> f64 {
        let i = self.at.get();
        let rec = self.log.get(i * 4..i * 4 + 4).unwrap_or_else(|| {
            panic!("call {i}: rust made more math calls than js ({f} {a} {b})")
        });
        let same = |x: f64, y: f64| x.to_bits() == y.to_bits() || (x.is_nan() && y.is_nan());
        if rec[0] != f || !same(rec[1], a) || !same(rec[2], b) {
            panic!(
                "call {i}: js did fn={} a={:?} b={:?}, rust did fn={} a={:?} b={:?}",
                rec[0], rec[1], rec[2], f, a, b
            );
        }
        self.at.set(i + 1);
        rec[3]
    }
}

impl MathFns for Replay {
    fn sin(&self, x: f64) -> f64 {
        self.take(SIN, x, 0.0)
    }
    fn cos(&self, x: f64) -> f64 {
        self.take(COS, x, 0.0)
    }
    fn atan2(&self, y: f64, x: f64) -> f64 {
        self.take(ATAN2, y, x)
    }
    fn pow(&self, x: f64, y: f64) -> f64 {
        self.take(POW, x, y)
    }
}
