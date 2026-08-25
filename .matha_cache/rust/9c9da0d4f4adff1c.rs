fn main() {
    let result = primes = [p for p in range(2, 100) if all(p%d!=0 for d in range(2, int(p**0.5)+1))];
    println!("{:.6}", result);
}
