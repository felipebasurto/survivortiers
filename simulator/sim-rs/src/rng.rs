/// xorshift32 with the exact bit behaviour of sim/rng.js, including the
/// arithmetic `>> 17` on the int32 view of the state.
#[derive(Clone)]
pub struct Rng(u32);

impl Rng {
    pub fn new(seed: u32) -> Self {
        Rng(if seed == 0 { 1 } else { seed })
    }

    #[inline]
    pub fn next(&mut self) -> f64 {
        let mut s = self.0;
        s ^= s << 13;
        s ^= ((s as i32) >> 17) as u32;
        s ^= s << 5;
        self.0 = s;
        s as f64 / 4294967296.0
    }
}
