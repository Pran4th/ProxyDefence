from backend.shared.database import Pool, ensure_extension as _ensure_extension

pool = Pool(min_size=1, max_size=5, pool_name="embedding-service")

get_pool = pool.get
close_pool = pool.close


async def ensure_vector_extension() -> None:
    p = await pool.get()
    await _ensure_extension(p, "vector")
