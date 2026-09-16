"use client";

import { useState } from "react";

import { AsyncView } from "@/components/async-view";
import { getReview } from "@/lib/api";
import type { ReviewBundle } from "@/lib/types";
import { useAsync } from "@/lib/use-async";
import { ReviewPage } from "@/views/review-view";

export function ReviewRoute({ id }: { id: string }) {
  const state = useAsync(() => getReview(id), id);
  return <AsyncView state={state}>{(initial) => <ReviewWithState key={initial.case.id} initial={initial} />}</AsyncView>;
}

function ReviewWithState({ initial }: { initial: ReviewBundle }) {
  const [data, setData] = useState(initial);
  return <ReviewPage data={data} onUpdated={setData} />;
}
