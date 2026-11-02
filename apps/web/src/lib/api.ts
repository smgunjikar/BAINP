export type Interpretation={case_id:string;status:string;reason:string;research_only:boolean;medical_diagnosis:null;disclaimer:string};
export type DemoCase={id:string;title:string;summary:string;interpretation:Interpretation;care_status:string;acute:boolean;functional:boolean;comparable:boolean;sessions:number;risks:boolean};
export type Timeline={participant_id:string;synthetic:boolean;sessions:Array<{id:string;recorded_at:string;correct:number;total:number;quality_status:string;mean_response_ms:number|null}>};
const BASE=process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';
export async function api<T>(path:string, init?:RequestInit):Promise<T> {
  const res=await fetch(`${BASE}${path}`,{...init,headers:{'Content-Type':'application/json',...(init?.headers||{})},cache:'no-store'});
  if(!res.ok){throw new Error(`API error ${res.status}: ${await res.text()}`)}
  return res.json() as Promise<T>;
}
