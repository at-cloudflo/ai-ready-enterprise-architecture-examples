from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path

PRODUCTS = ["PMP-7", "PMP-8", "VAL-2"]
PRICES = {"PMP-7":1200,"PMP-8":1800,"VAL-2":600}

def generate(output_dir: Path, count: int = 100, seed: int = 2026) -> None:
    if count < 1 or count > 100000:
        raise ValueError("count must be between 1 and 100000")
    output_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    customers = [{"customer_id":f"SYN-C-{i:04d}",
                  "customer_name":f"Synthetic Buyer {i:04d}",
                  "tier":("Strategic" if i%5==0 else "Standard")}
                 for i in range(1, max(6, count//4)+1)]
    orders = []
    lines = []
    for idx in range(1,count+1):
        order_id = f"SYN-SO-{idx:06d}"
        customer_id = rng.choice(customers)["customer_id"]
        status = rng.choices(["open","fulfilled"],weights=[3,1])[0]
        orders.append({"order_id":order_id,"customer_id":customer_id,
                       "order_status":status,"promised_day":rng.randrange(7,45)})
        for line_id in range(1,rng.randrange(2,4)):
            product = rng.choice(PRODUCTS)
            units = rng.randint(1,5)
            lines.append({"order_id":order_id,"line_id":line_id,
                          "product_id":product,"quantity":units,
                          "unit_price_usd":PRICES[product],"discount_usd":0})
    def write(name,rows):
        with (output_dir/name).open("w",newline="",encoding="utf-8") as handle:
            writer = csv.DictWriter(handle,fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    write("customers.csv",customers)
    write("orders.csv",orders)
    write("order_lines.csv",lines)

def main() -> None:
    p=argparse.ArgumentParser(description="Generate synthetic ForgeWorks order samples")
    p.add_argument("--count",type=int,default=100)
    p.add_argument("--seed",type=int,default=2026)
    p.add_argument("--output",type=Path,default=Path("generated-data"))
    args=p.parse_args()
    generate(args.output,args.count,args.seed)
    print(f"Generated {args.count} synthetic orders into {args.output}")

if __name__=="__main__":
    main()
