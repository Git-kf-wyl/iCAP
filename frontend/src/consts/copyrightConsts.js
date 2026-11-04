export const evaluator_list={includes:()=>!!localStorage.getItem('ic_token')};
export const manager_list={includes:()=>localStorage.getItem('ic_role')==='admin'};
