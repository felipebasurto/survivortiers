/// Every transcendental call the engine makes goes through this trait.
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
