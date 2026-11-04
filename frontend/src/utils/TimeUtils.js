function getLocalISOString() {
    const tzOffset = new Date().getTimezoneOffset() * 60000; // 以毫秒为单位
    return new Date(Date.now() - tzOffset).toISOString();
}

export {
    getLocalISOString
}