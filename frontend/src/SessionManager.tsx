import {useState} from 'react';
import {ArrowUpRight, Play, Trash2, X} from 'lucide-react';
import {matchStatus, friendlyError} from './CoachingInsights';
import type {Session} from './main';

type Props = {
  sessions: Session[];
  onOpen: (session:Session)=>void;
  onDelete: (session:Session)=>Promise<void>;
  onCreate: ()=>void;
};

export function SessionManager({sessions,onOpen,onDelete,onCreate}:Props){
  const [target,setTarget]=useState<Session|null>(null);
  const [deleting,setDeleting]=useState(false);
  const [error,setError]=useState('');
  async function confirmDelete(){
    if(!target)return;
    setDeleting(true);setError('');
    try{await onDelete(target);setTarget(null);}
    catch(error){setError(friendlyError((error as Error).message));}
    finally{setDeleting(false);}
  }
  return <>
    <div className="panel session-manager">
      <div className="panel-title"><h2>Manage sessions</h2><span>{sessions.length} sessions</span></div>
      {sessions.length?sessions.map(session=>{
        const active=['queued','loading','processing','encoding','deleting'].includes(session.status);
        return <div className="managed-session" key={session.id}>
          <button className="session-open" onClick={()=>onOpen(session)}>
            <span className="session-symbol"><Play size={20}/></span>
            <span><b>{session.name}</b><small>{session.sport} · {new Date(session.updated_at).toLocaleString()}</small></span>
            <span className="tag">{matchStatus(session.status)}</span><ArrowUpRight size={17}/>
          </button>
          <button className="delete-session" disabled={active} title={active?'Stop analysis before deleting':'Delete session and its files'} aria-label={`Delete ${session.name}`} onClick={()=>{setTarget(session);setError('');}}><Trash2 size={15}/> Delete</button>
        </div>;
      }):<div className="empty-small">No saved sessions.<button className="secondary" onClick={onCreate}>Create session</button></div>}
    </div>
    {target&&<div className="modal-backdrop"><section className="modal" role="dialog" aria-modal="true" aria-labelledby="delete-heading">
      <div className="panel-title"><h2 id="delete-heading">Delete this session?</h2><button className="icon-button" disabled={deleting} aria-label="Cancel deletion" onClick={()=>setTarget(null)}><X size={18}/></button></div>
      <p><b>{target.name}</b></p><p>This permanently deletes its processed video, previews, statistics and uploaded source when no other session uses it. This cannot be undone.</p>
      {error&&<div role="alert" className="alert">{error}</div>}
      <div className="delete-actions"><button className="secondary" disabled={deleting} onClick={()=>setTarget(null)}>Keep session</button><button className="danger" disabled={deleting} onClick={confirmDelete}>{deleting?'Deleting…':'Permanently delete'}</button></div>
    </section></div>}
  </>;
}
