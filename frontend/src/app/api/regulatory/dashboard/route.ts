import { NextResponse } from "next/server";

import { loadRegulatoryDashboardData } from "../../../../lib/regulatoryData";

export const dynamic = "force-dynamic";

export async function GET() {
  const payload = await loadRegulatoryDashboardData();
  return NextResponse.json(payload);
}
